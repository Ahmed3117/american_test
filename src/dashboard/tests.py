from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from course.models import Course, Unit
from exam.models import Exam, ExamQuestion


class DashboardQuestionWorkflowTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff",
            password="pass1234",
            name="Staff",
            user_type="admin",
            is_staff=True,
        )
        self.client.force_authenticate(self.staff)
        self.course = Course.objects.create(name="Math")
        self.unit = Unit.objects.create(course=self.course, name="Algebra")

    def test_staff_can_create_question_with_answers_and_assign_to_exam(self):
        question_response = self.client.post(
            "/dashboard/questions/",
            {
                "text": "2 + 2 = ?",
                "points": 3,
                "difficulty": "EASY",
                "unit": self.unit.id,
                "question_type": "MCQ",
                "answers": [
                    {"text": "4", "is_correct": True},
                    {"text": "5", "is_correct": False},
                ],
            },
            format="json",
        )
        self.assertEqual(question_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(question_response.data["answers"]), 2)

        exam = Exam.objects.create(
            title="Unit Exam",
            related_to="UNIT",
            unit=self.unit,
            number_of_questions=1,
            time_limit=30,
            start=timezone.now(),
            end=timezone.now() + timezone.timedelta(days=1),
        )

        assign_response = self.client.post(
            f"/dashboard/exams/{exam.id}/questions/",
            {"question_ids": [question_response.data["id"]]},
            format="json",
        )
        self.assertEqual(assign_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ExamQuestion.objects.filter(exam=exam, question_id=question_response.data["id"]).exists())

        exam.refresh_from_db()
        self.assertEqual(exam.number_of_questions, 1)
        self.assertEqual(exam.score, 3)

    def test_staff_can_create_course_level_question_and_exam(self):
        question_response = self.client.post(
            "/dashboard/questions/",
            {
                "text": "Which test is this platform preparing students for?",
                "points": 2,
                "difficulty": "EASY",
                "course": self.course.id,
                "question_type": "MCQ",
                "answers": [
                    {"text": "EST", "is_correct": True},
                    {"text": "IELTS", "is_correct": False},
                ],
            },
            format="json",
        )
        self.assertEqual(question_response.status_code, status.HTTP_201_CREATED)

        exam_response = self.client.post(
            "/dashboard/exams/",
            {
                "title": "Course Exam",
                "related_to": "COURSE",
                "course": self.course.id,
                "number_of_questions": 1,
                "time_limit": 30,
                "start": timezone.now(),
                "end": timezone.now() + timezone.timedelta(days=1),
            },
            format="json",
        )
        self.assertEqual(exam_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(exam_response.data["related_course"], self.course.id)
        self.assertIsNone(exam_response.data["related_unit"])
