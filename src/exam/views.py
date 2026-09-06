# RestFrameWork lib
import random
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework import generics
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone
from django.db.models import Count, Min, Max
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Prefetch
# custom filters
from exam.filters import RelatedCourseFilterBackend, StudentBankFilter
# Models
from .serializers import (
    ExamSerializer,
    QuestionSerializerWithCorrectAnswer,
    QuestionSerializerWithoutCorrectAnswer,
    StudentBankSerializer,
    StudentExamResultSerializer,
    StudentQuestionCategoryOptionSerializer,
    StudentUnitOptionSerializer,
    StudentYearOptionSerializer,
    TempExamCreateSerializer,
    TempExamDetailSerializer,
    TempExamListSerializer,
)
from .models import AddReasonChoices, Answer, Exam, ExamQuestion, Question, QuestionCategory, QuestionType, Result, ResultTrial, StudentBank, Submission, TempExam, Year
from course.models import Course, Unit
from student.models import Student
from .serializer_fields import stored_file_url
from .services import (
    main_exam_quota_status,
    temp_exam_quota_status,
    trial_quota_status,
    unsubscribed_trial_quota_status,
)


class HasStudentProfile(BasePermission):
    message = 'A student account is required.'

    def has_permission(self, request, view):
        return hasattr(request.user, 'student')


class StudentQuestionCategoryOptionListView(generics.ListAPIView):
    serializer_class = StudentQuestionCategoryOptionSerializer
    permission_classes = [IsAuthenticated, HasStudentProfile]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course']
    pagination_class = None
    queryset = QuestionCategory.objects.only(
        'id', 'title', 'course_id'
    ).order_by('title', 'id')


class StudentUnitOptionListView(generics.ListAPIView):
    serializer_class = StudentUnitOptionSerializer
    permission_classes = [IsAuthenticated, HasStudentProfile]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course']
    pagination_class = None
    queryset = Unit.objects.filter(is_active=True).only(
        'id', 'name', 'course_id', 'order'
    ).order_by('order', 'name', 'id')


class StudentYearOptionListView(generics.ListAPIView):
    serializer_class = StudentYearOptionSerializer
    permission_classes = [IsAuthenticated, HasStudentProfile]
    pagination_class = None
    queryset = Year.objects.only('id', 'value').order_by('-value', 'id')


def _question_explanation_fields(question, prefix="question_explanation"):
    if not question:
        return {
            f"{prefix}_text": None,
            f"{prefix}_video_url": None,
            f"{prefix}_recorded_audio": None,
        }
    return {
        f"{prefix}_text": question.explanation_text,
        f"{prefix}_video_url": stored_file_url(question.explanation_video_url),
        f"{prefix}_recorded_audio": question.explanation_recorded_audio.url if question.explanation_recorded_audio else None,
    }


def _question_images_payload(question):
    """Serialize QuestionImage rows for manual payload building."""
    if not question:
        return []
    return [
        {"id": qi.id, "image": qi.image.url}
        for qi in question.images.all()
    ]


def _first_question_image_url(question):
    """Convenience single-image URL = first row of the new images model."""
    if not question:
        return None
    first = question.images.first()
    return first.image.url if first else None


class StudentExamListCreateView(generics.ListCreateAPIView):
    """List and create the authenticated student's main exams."""
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated, HasStudentProfile]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["course", "unit", "category", "years"]
    search_fields = ["title", "course__name", "unit__name", "category__title", "years__value"]
    ordering_fields = ["created", "title", "number_of_questions", "time_limit"]
    ordering = ["-created", "-id"]

    def get_queryset(self):
        return (
            Exam.objects.filter(student=self.request.user.student)
            .select_related("student", "course", "unit", "category")
            .prefetch_related("years", "exam_questions")
            .distinct()
        )


class StudentExamDetailView(generics.RetrieveAPIView):
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get_queryset(self):
        return Exam.objects.filter(student=self.request.user.student).select_related(
            'student', 'course', 'unit', 'category'
        ).prefetch_related('years', 'exam_questions')


class ExamConfigStatusView(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get(self, request):
        student = request.user.student
        course_id = request.query_params.get('course')
        if course_id:
            course = get_object_or_404(Course, pk=course_id, is_active=True)
            payload = main_exam_quota_status(student, course)
            payload['temp_exam'] = temp_exam_quota_status(student)
            return Response(payload)

        # Keep the original subscribed quota fields at the root for backward
        # compatibility and expose the guest allowance alongside them.
        payload = trial_quota_status(student)
        payload['access_type'] = 'subscribed'
        payload['unsubscribed'] = unsubscribed_trial_quota_status(student)
        payload['temp_exam'] = temp_exam_quota_status(student)
        return Response(payload)


class CheckExamStartAbility(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get(self, request, exam_id):
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id, student=student)

        try:
            result = Result.objects.get(student=student, exam=exam)

            unsubmitted_trial = (
                result.trials
                .filter(trial=result.trial)
                .filter(student_submitted_exam_at__isnull=True)
                .first()
            )

            if unsubmitted_trial:
                return Response({
                    "status": "trial_unsubmitted",
                    "status_message": "لديك محاولة غير مكتملة",
                    "trial": {
                        "id": unsubmitted_trial.id,
                        "trial_number": unsubmitted_trial.trial,
                        "started_at": unsubmitted_trial.student_started_exam_at,
                    },
                    "quota": main_exam_quota_status(
                        student,
                        exam.course,
                        exam.number_of_questions,
                    ),
                }, status=status.HTTP_200_OK)

        except Result.DoesNotExist:
            pass

        quota = main_exam_quota_status(
            student,
            exam.course,
            exam.number_of_questions,
        )
        return Response({
            "status": "can_start" if quota['can_start'] else "quota_reached",
            "status_message": "يمكنك البدء" if quota['can_start'] else "تم بلوغ الحد المسموح للمحاولات",
            "quota": quota,
        })

class StartExam(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def _get_exam_questions(self, exam):
        relations = list(
            ExamQuestion.objects
            .filter(exam=exam, is_active=True)
            .select_related("question")
            .prefetch_related("question__answers", "question__years", "question__images")
            .order_by('order', 'id')
        )
        return [relation.question for relation in relations]

    @transaction.atomic
    def get(self, request, exam_id: int) -> Response:
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id, student=student)
        student = Student.objects.select_for_update().get(pk=student.pk)

        questions = self._get_exam_questions(exam)
        if len(questions) != exam.number_of_questions:
            return Response(
                {"error": "The exam question set is incomplete."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = Result.objects.filter(student=student, exam=exam).first()
        unsubmitted_trial = None
        if result:
            unsubmitted_trial = result.trials.filter(
                student_submitted_exam_at__isnull=True
            ).order_by('-trial').first()

        if unsubmitted_trial:
            result_trial = unsubmitted_trial
            resuming = True
        else:
            quota = main_exam_quota_status(
                student,
                exam.course,
                exam.number_of_questions,
            )
            if not quota['can_start']:
                return Response(
                    {"error": "Trial quota reached.", "quota": quota},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            if result is None:
                result = Result.objects.create(student=student, exam=exam, trial=0)
            result.trial += 1
            result.save(update_fields=['trial'])
            result_trial = ResultTrial.objects.create(
                result=result,
                trial=result.trial,
                student_started_exam_at=timezone.now(),
                submitted_by_unsubscribed_user=(
                    quota['access_type'] == 'unsubscribed'
                ),
            )
            resuming = False

        question_data = QuestionSerializerWithoutCorrectAnswer(
            questions,
            many=True,
            context={"request": request, "main_exam": True},
        ).data
        return Response({
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_time_limit": exam.time_limit,
            "questions": question_data,
            "resuming": resuming,
            "trial_id": result_trial.id,
            "started_at": result_trial.student_started_exam_at,
        })

class SubmitExam(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]
    parser_classes = [MultiPartParser]

    @transaction.atomic
    def post(self, request, exam_id):
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id, student=student)
        submit_type = request.data.get("submit_type", "student_submit")
        
        # Add idempotency key to prevent duplicate submissions from network retries
        idempotency_key = request.META.get('HTTP_X_IDEMPOTENCY_KEY')
        if not idempotency_key:
            # Generate a unique key based on request content if not provided
            import hashlib
            content_hash = hashlib.md5(str(sorted(request.data.items())).encode()).hexdigest()
            idempotency_key = f"{student.id}_{exam_id}_{content_hash}"

        # Validate every question reference sent by the frontend. The actual
        # grading loop below uses the complete frozen exam question set so a
        # question omitted from the payload is still recorded as unanswered.
        submitted_question_ids = set()
        for key in request.data.keys():
            try:
                if key.startswith('question_id_'):
                    submitted_question_ids.add(int(key.rsplit('_', 1)[-1]))
                elif key.startswith('selected_answer_id_'):
                    submitted_question_ids.add(int(key.rsplit('_', 1)[-1]))
                elif key == 'question_id':
                    submitted_question_ids.add(int(request.data[key]))
            except (TypeError, ValueError):
                return Response(
                    {"error": f"Invalid question reference: {key}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        exam_questions = {
            question.id: question
            for question in Question.objects.filter(
                question_type=QuestionType.MCQ,
                exam_questions__exam=exam,
                exam_questions__is_active=True,
            ).distinct()
        }
        if not exam_questions:
            return Response(
                {"error": "This exam has no active MCQ questions."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invalid_question_ids = sorted(
            submitted_question_ids - set(exam_questions)
        )
        if invalid_question_ids:
            return Response(
                {
                    "error": "All submitted questions must be MCQs from this exam.",
                    "invalid_question_ids": invalid_question_ids,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Submissions are only valid after StartExam has created the result and
        # its current trial. Missing state is a client-flow error, not a server
        # failure.
        result = Result.objects.select_for_update().filter(
            student=student,
            exam=exam,
        ).first()
        if result is None:
            return Response(
                {"error": "يجب بدء الامتحان قبل إرسال الإجابات"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result_trial = result.trials.select_for_update().filter(
            trial=result.trial
        ).first()
        if result_trial is None:
            return Response(
                {"error": "لم يتم العثور على محاولة نشطة لهذا الامتحان"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # prevent duplicate submissions for completed trials
        if result_trial.student_submitted_exam_at is not None:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Duplicate submission attempt - Student: {student.id}, Exam: {exam_id}, Trial: {result.trial}")
            return Response(
                {"error": "لقد أنهيت هذه المحاولة بالفعل، ابدأ محاولة جديدة"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Process each question using update_or_create for better performance
        for question_id, question in exam_questions.items():
            if question.question_type == QuestionType.MCQ:
                # Process MCQ answer
                selected_answer_id = request.data.get(f"selected_answer_id_{question_id}")
                # Handle null/empty string case
                if selected_answer_id in [None, "", "null"]:
                    # Update or create submission with no answer
                    submission, created = Submission.objects.update_or_create(
                        student=student,
                        exam=exam,
                        question=question,
                        result_trial=result_trial,
                        defaults={
                            'selected_answer': None,
                            'is_solved': False,
                            'is_correct': False
                        }
                    )
                    StudentBank.objects.update_or_create(
                        student=student,
                        question=question,
                        defaults={
                            "add_reason": AddReasonChoices.UNSOLVED,
                            "is_solved_now": False,
                        },
                    )
                    continue
                try:
                    
                    selected_answer = get_object_or_404(
                        Answer,
                        pk=selected_answer_id,
                        question=question
                    )
                    # Update or create submission with the selected answer
                    submission, created = Submission.objects.update_or_create(
                        student=student,
                        exam=exam,
                        question=question,
                        result_trial=result_trial,
                        defaults={
                            'selected_answer': selected_answer,
                            'is_solved': True,
                            'is_correct': selected_answer.is_correct
                        }
                    )

                    
                    if not submission.is_correct:

                        StudentBank.objects.update_or_create(
                            student=student,
                            question=question,
                            defaults={
                                "add_reason": AddReasonChoices.INCORRECT,
                                "is_solved_now": False,
                            },
                        )

                except (ValueError, Http404):
                    # Handle invalid answer ID
                    # Update or create submission with no answer
                    submission, created = Submission.objects.update_or_create(
                        student=student,
                        exam=exam,
                        question=question,
                        result_trial=result_trial,
                        defaults={
                            'selected_answer': None,
                            'is_solved': False,
                            'is_correct': False
                        }
                    )
                    StudentBank.objects.update_or_create(
                        student=student,
                        question=question,
                        defaults={
                            "add_reason": AddReasonChoices.UNSOLVED,
                            "is_solved_now": False,
                        },
                    )
        # Calculate scores
        try:
            total_score = Submission.objects.filter(
                result_trial=result_trial,
                is_correct=True
            ).count()
            exam_score = result.exam.exam_questions.filter(is_active=True).count()

            # Update trial and result
            result_trial.score = total_score
            result_trial.exam_score = exam_score
            result_trial.student_submitted_exam_at = timezone.now()
            result_trial.submit_type = submit_type
            result_trial.save()

        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating score for student {student.id}, exam {exam_id}: {str(e)}")
            
            return Response(
                {"error": f"Error calculating score: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Log successful submission
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Exam submission successful - Student: {student.id}, Exam: {exam_id}, Trial: {result.trial}, Score: {total_score}, Idempotency Key: {idempotency_key}")

        return Response({
            "message": "تم إرسال الإجابات بنجاح",
            "score": total_score,
            "is_succeeded": total_score >= (Exam.PASSING_PERCENT / 100) * result_trial.exam_score,
            "trial": result.trial
        }, status=status.HTTP_200_OK)


class StudentExamResultsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]
    serializer_class = StudentExamResultSerializer
    filter_backends = [DjangoFilterBackend, RelatedCourseFilterBackend]
    filterset_fields = ['exam__course', 'exam__unit', 'exam__category']

    def get_queryset(self):
        student = self.request.user.student
        return Result.objects.filter(
            student=student,
            trials__isnull=False,
        ).select_related(
            'exam', 
            'exam__course',
            'exam__unit',
            'student',
            'student__user',
        ).prefetch_related(
            Prefetch(
                'trials',
                queryset=ResultTrial.objects.order_by('-trial')
            ),
            Prefetch(
                'exam__exam_questions',
                queryset=ExamQuestion.objects.select_related('question')
            ),
        ).distinct().order_by('-added')


class GetMyExamResult(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get(self, request, exam_id):
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id)

        # Ensure result visibility
        # if timezone.now() < exam.allow_show_results_at:
        #     return Response(
        #         {"error": "You are not allowed to see this exam result yet"},
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # Fetch the result and active trial
        result = get_object_or_404(Result, student=student, exam=exam)
        active_trial = result.active_trial
        if not active_trial:
            return Response(
                {"error": "No trial exists for this exam result."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Fetch MCQ submissions and prefetch correct answers for each question
        mcq_submissions = Submission.objects.filter(
            student=student, exam=exam, result_trial=active_trial
        ).select_related(
            'question', 'selected_answer', 'question__category'
        ).prefetch_related(
            Prefetch(
                'question__answers',
                queryset=Answer.objects.filter(is_correct=True),
                to_attr='correct_answers_list'  # Custom attribute to store the result
            )
        )

        # Calculate counts
        correct_mcq_count = mcq_submissions.filter(is_correct=True).count()
        incorrect_mcq_count = mcq_submissions.filter(is_correct=False, is_solved=True).count()
        unsolved_mcq_count = mcq_submissions.filter(is_solved=False).count()

        student_answers = []

        # Process MCQ submissions
        for submission in mcq_submissions:
            question = submission.question
            selected_answer = submission.selected_answer

            # Fetch all answers for the question
            answers = Answer.objects.filter(question=question)
            answer_details = [
                {
                    "id": ans.id,
                    "text": ans.text,
                    "image": ans.image.url if ans.image else None,
                    "is_correct": ans.is_correct
                }
                for ans in answers
            ]

            # Construct the selected answer object
            selected_answer_obj = None
            if selected_answer:
                selected_answer_obj = {
                    "id": submission.selected_answer.id,
                    "text": selected_answer.text,
                    "image": selected_answer.image.url if selected_answer.image else None,
                    "is_correct": selected_answer.is_correct
                }

            answer_data = {
                "submission_id": submission.id,
                "type": "mcq",
                "question_id": question.id if question else None,
                "question_category": question.category.title if question and question.category else None,
                "question_category_id": question.category.id if question and question.category else None,
                "question_text": question.text if question else None,
                "question_image": _first_question_image_url(question),
                "question_images": _question_images_payload(question),
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ] if question else [],
                **_question_explanation_fields(question),
                "selected_answer": selected_answer_obj,  # Updated to include full object
                "is_correct": submission.is_correct if submission.is_correct is not None else False,
                "is_solved": submission.is_solved if submission.is_solved is not None else False,
                "points": 1,
                "answers": answer_details  # Include all answers here
            }
            student_answers.append(answer_data)

            # if not submission.is_solved:
            #     unsolved_questions.append(answer_data)

        # Response payload
        response_data = {
            "active_trial": active_trial.id,
            "trial_number": active_trial.trial,
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_description": None,
            "exam_score": active_trial.exam_score if active_trial else 0,
            "student_score": active_trial.score if active_trial else 0,
            "is_succeeded": result.is_succeeded,
            "student_trials": result.trial,
            "is_trials_finished": result.is_trials_finished,
            # Counts
            "number_of_mcq": mcq_submissions.count(),
            "correct_mcq_count": correct_mcq_count,
            "incorrect_mcq_count": incorrect_mcq_count,
            "unsolved_mcq_count": unsolved_mcq_count,
            # Other data
            "student_answers": student_answers,
            "student_started_exam_at": active_trial.student_started_exam_at if active_trial else None,
            "student_submitted_exam_at": active_trial.student_submitted_exam_at if active_trial else None,
            "submit_type": active_trial.submit_type if active_trial else None,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class GetMyExamResultForTrial(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def get(self, request, exam_id, result_trial_id):
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id)

        # Fetch the specific trial and ensure it belongs to the student and exam
        trial = get_object_or_404(
            ResultTrial.objects.select_related('result', 'result__exam', 'result__student'),
            pk=result_trial_id,
            result__student=student,
            result__exam=exam
        )

        # Fetch MCQ submissions and prefetch correct answers for each question
        mcq_submissions = Submission.objects.filter(
            result_trial=trial
        ).select_related(
            'question', 'selected_answer', 'question__category'
        ).prefetch_related(
            Prefetch(
                'question__answers',
                queryset=Answer.objects.filter(is_correct=True),
                to_attr='correct_answers_list'
            )

        ).order_by("id")


        # Calculate counts
        correct_mcq_count = mcq_submissions.filter(is_correct=True).count()
        incorrect_mcq_count = mcq_submissions.filter(is_correct=False, is_solved=True).count()
        unsolved_mcq_count = mcq_submissions.filter(is_solved=False).count()

        student_answers = []

        # Process MCQ submissions
        for submission in mcq_submissions:
            question = submission.question
            selected_answer = submission.selected_answer

            # Fetch all answers for the question
            answers = Answer.objects.filter(question=question)
            answer_details = [
                {
                    "id": ans.id,
                    "text": ans.text,
                    "image": ans.image.url if ans.image else None,
                    "is_correct": ans.is_correct
                }
                for ans in answers
            ]

            # Construct the selected answer object
            selected_answer_obj = None
            if selected_answer:
                selected_answer_obj = {
                    "id": submission.selected_answer.id,
                    "text": selected_answer.text,
                    "image": selected_answer.image.url if selected_answer.image else None,
                    "is_correct": selected_answer.is_correct
                }

            answer_data = {
                "submission_id": submission.id,
                "type": "mcq",
                "question_id": question.id if question else None,
                "question_category": question.category.title if question and question.category else None,
                "question_category_id": question.category.id if question and question.category else None,
                "question_text": question.text if question else None,
                "question_image": _first_question_image_url(question),
                "question_images": _question_images_payload(question),
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ] if question else [],
                **_question_explanation_fields(question),
                "selected_answer": selected_answer_obj,
                "is_correct": submission.is_correct if submission.is_correct is not None else False,
                "is_solved": submission.is_solved if submission.is_solved is not None else False,
                "points": 1,
                "answers": answer_details
            }
            student_answers.append(answer_data)

        # Determine if the student succeeded in this trial
        is_succeeded = False
        if trial.exam_score and trial.score is not None:
            is_succeeded = trial.score >= (Exam.PASSING_PERCENT / 100) * trial.exam_score

        # Response payload
        response_data = {
            "active_trial": trial.id,
            "trial_number": trial.trial,
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_description": None,
            "exam_score": trial.exam_score if trial else 0,
            "student_score": trial.score if trial else 0,
            "is_succeeded": is_succeeded,
            "student_trials": trial.result.trial if trial else 0,
            "is_trials_finished": trial.result.is_trials_finished if trial else False,
            # Counts
            "number_of_mcq": mcq_submissions.count(),
            "correct_mcq_count": correct_mcq_count,
            "incorrect_mcq_count": incorrect_mcq_count,
            "unsolved_mcq_count": unsolved_mcq_count,
            # Other data
            "student_answers": student_answers,
            "student_started_exam_at": trial.student_started_exam_at if trial else None,
            "student_submitted_exam_at": trial.student_submitted_exam_at if trial else None,
            "submit_type": trial.submit_type if trial else None,
            
        }

        return Response(response_data, status=status.HTTP_200_OK)


#^-------------------------------- {Student Temp Exams} ---------------------------------#

class StudentBankListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]
    serializer_class = StudentBankSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = StudentBankFilter
    search_fields = ['question__text']

    def get_queryset(self):
        student = self.request.user.student
        
        # Load the complete normal question payload, including the new
        # QuestionImage relation, without per-row answer/image/year queries.
        queryset = StudentBank.objects.filter(student=student).select_related(
            'question',
            'question__course',
            'question__unit', 
            'question__category'
        ).prefetch_related(
            'question__answers',
            'question__images',
            'question__years',
        )
        
        return queryset.distinct().order_by('-created')

class CreateTempExam(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    def _sample_student_banks(self, base_queryset, k):
        """Select exactly ``k`` mistake rows and preload their question payload."""
        qs = base_queryset
        agg = qs.aggregate(min_id=Min('id'), max_id=Max('id'), total_count=Count('id'))
        min_id, max_id, total_count = agg.get('min_id'), agg.get('max_id'), agg.get('total_count', 0)

        if min_id is None or max_id is None or total_count == 0:
            return []

        chosen_ids = set()
        if total_count <= k * 2:
            all_ids = list(qs.values_list('id', flat=True))
            chosen_ids = set(random.sample(all_ids, min(k, len(all_ids))))
        else:
            attempts = 0
            max_attempts = min(k * 5, 200)
            while len(chosen_ids) < k and attempts < max_attempts:
                r = random.randint(min_id, max_id)
                candidate = qs.filter(id__gte=r).values_list('id', flat=True).first()
                if candidate is None and r > min_id:
                    candidate = qs.filter(id__lt=r).order_by('-id').values_list('id', flat=True).first()
                if candidate is not None:
                    chosen_ids.add(candidate)
                attempts += 1

        # Sparse ID ranges can make probing return fewer than requested. Fill
        # the remainder deterministically without loading the whole bank.
        if len(chosen_ids) < k:
            missing = k - len(chosen_ids)
            fallback_ids = qs.exclude(id__in=chosen_ids).order_by('id').values_list(
                'id', flat=True
            )[:missing]
            chosen_ids.update(fallback_ids)

        chosen_ids = list(chosen_ids)
        random.shuffle(chosen_ids)
        bank_items = {
            item.id: item
            for item in (
                StudentBank.objects.filter(id__in=chosen_ids)
                .select_related(
                    'question',
                    'question__course',
                    'question__unit',
                    'question__category',
                )
                .prefetch_related(
                    'question__answers',
                    'question__images',
                    'question__years',
                )
            )
        }
        return [bank_items[item_id] for item_id in chosen_ids if item_id in bank_items]

    @transaction.atomic
    def post(self, request):
        # Serialize concurrent creations for one student so two requests cannot
        # both pass the same calendar-quota check.
        student = Student.objects.select_for_update().get(
            pk=request.user.student.pk
        )
        serializer = TempExamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        number_of_questions = data['number_of_questions']
        course = data.get('course')
        unit = data.get('unit')
        category = data.get('category')
        years = data.get('years', [])
        add_reason = data.get('add_reason')
        selected_questions_type = data.get('selected_questions_type')

        quota = temp_exam_quota_status(student)
        if not quota['can_start']:
            return Response(
                {"error": "Temp exam quota reached.", "quota": quota},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Build optimized base queryset with early filtering and minimal field selection
        queryset = StudentBank.objects.filter(
            student=student,
            question__question_type=QuestionType.MCQ,
            question__is_active=True
        ).select_related('question').only(
            'id', 'student_id', 'question_id', 'is_solved_now',
            'question__id', 'question__question_type', 'question__is_active'
        )

        # Apply filters with indexed field optimization
        if selected_questions_type == 'solved':
            queryset = queryset.filter(is_solved_now=True)
        elif selected_questions_type == 'not_solved':
            queryset = queryset.filter(is_solved_now=False)

        if add_reason:
            queryset = queryset.filter(add_reason=add_reason)
        if course:
            queryset = queryset.filter(question__course=course)
        if unit:
            queryset = queryset.filter(question__unit=unit)
        if category:
            queryset = queryset.filter(question__category=category)
        if years:
            queryset = queryset.filter(question__years__in=years).distinct()

        # Fast count using optimized queryset
        total_available = queryset.count()
        if total_available < number_of_questions:
            return Response(
                {"error": f"Not enough questions available. Found {total_available}, required {number_of_questions}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Select the exact mistake questions. Similar-question substitution is
        # intentionally not used for student temp exams.
        selected_student_banks = self._sample_student_banks(queryset, number_of_questions)
        if len(selected_student_banks) < number_of_questions:
            return Response(
                {
                    "error": (
                        "Could not select enough unique mistake questions. "
                        f"Selected {len(selected_student_banks)}, "
                        f"required {number_of_questions}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        temp_exam = TempExam.objects.create(
            student=student,
            course=course,
            unit=unit,
            category=category,
            number_of_questions=number_of_questions,
            time_limit=data['time_limit'],
            selected_questions_type=selected_questions_type,
            add_reason=add_reason,
        )
        temp_exam.years.set(years)
        temp_exam.student_bank_items.set(selected_student_banks)

        final_questions = [
            student_bank.question for student_bank in selected_student_banks
        ]
        question_data = QuestionSerializerWithCorrectAnswer(
            final_questions,
            many=True,
            context={"request": request},
        ).data

        return Response({
            "temp_exam_id": temp_exam.id,
            "number_of_questions": temp_exam.number_of_questions,
            "time_limit": temp_exam.time_limit,
            "course": temp_exam.course.id if temp_exam.course else None,
            "unit": temp_exam.unit.id if temp_exam.unit else None,
            "category": temp_exam.category.id if temp_exam.category else None,
            "years": [year.id for year in years],
            "add_reason": temp_exam.add_reason,
            "selected_questions_type": temp_exam.selected_questions_type,
            "questions": question_data,
            "quota": temp_exam_quota_status(student),
        }, status=status.HTTP_201_CREATED)


def _student_temp_exam_queryset(student):
    bank_items = StudentBank.objects.select_related(
        'question',
        'question__course',
        'question__unit',
        'question__category',
    ).prefetch_related(
        'question__answers',
        'question__images',
        'question__years',
    ).order_by('id')
    return TempExam.objects.filter(student=student).select_related(
        'course', 'unit', 'category'
    ).prefetch_related(
        'years',
        Prefetch('student_bank_items', queryset=bank_items),
    ).order_by('-created', '-id')


class StudentTempExamListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]
    serializer_class = TempExamListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'course',
        'unit',
        'category',
        'years',
        'add_reason',
        'selected_questions_type',
    ]
    search_fields = [
        'course__name',
        'unit__name',
        'category__title',
        'years__value',
        'student_bank_items__question__text',
    ]
    ordering_fields = ['created', 'number_of_questions', 'time_limit', 'result']
    ordering = ['-created', '-id']

    def get_queryset(self):
        return _student_temp_exam_queryset(self.request.user.student).distinct()


class StudentTempExamDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]
    serializer_class = TempExamDetailSerializer

    def get_queryset(self):
        return _student_temp_exam_queryset(self.request.user.student)


class SubmitTempExamResults(APIView):
    permission_classes = [IsAuthenticated, HasStudentProfile]

    @transaction.atomic
    def post(self, request):
        student = request.user.student
        temp_exam_id = request.data.get('temp_exam_id')
        correct_question_ids = request.data.get('correct_question_ids', [])
        result = request.data.get('result')

        # Validate inputs early
        if not temp_exam_id:
            return Response(
                {"error": "temp_exam_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            temp_exam_id = int(temp_exam_id)
        except (TypeError, ValueError):
            return Response(
                {"error": "temp_exam_id must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if correct_question_ids is None:
            correct_question_ids = []
        if not isinstance(correct_question_ids, (list, tuple)):
            return Response(
                {"error": "correct_question_ids must be a list of question IDs"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            correct_question_ids = sorted({
                int(question_id) for question_id in correct_question_ids
            })
        except (TypeError, ValueError):
            return Response(
                {"error": "correct_question_ids must contain valid integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if any(question_id <= 0 for question_id in correct_question_ids):
            return Response(
                {"error": "correct_question_ids must contain positive integers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if result is None:
            return Response(
                {"error": "result is required and must be the raw correct-answer count."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            numeric_result = float(result)
        except (ValueError, TypeError):
            return Response(
                {"error": "result must be a whole-number raw score."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not numeric_result.is_integer():
            return Response(
                {"error": "result must be a whole-number raw score."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result_score = int(numeric_result)
        if result_score < 0:
            return Response(
                {"error": "result cannot be less than zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temp_exam = get_object_or_404(
            TempExam.objects.select_for_update().only(
                'id', 'student_id', 'result', 'number_of_questions'
            ),
            id=temp_exam_id,
            student=student
        )

        selected_question_ids = set(
            temp_exam.student_bank_items.values_list('question_id', flat=True)
        )
        invalid_question_ids = sorted(
            set(correct_question_ids) - selected_question_ids
        )
        if invalid_question_ids:
            return Response(
                {
                    "error": "All correct questions must belong to this temp exam.",
                    "invalid_question_ids": invalid_question_ids,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if result_score > temp_exam.number_of_questions:
            return Response(
                {
                    "error": (
                        "result cannot exceed the temp exam question count "
                        f"({temp_exam.number_of_questions})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result_score != len(correct_question_ids):
            return Response(
                {
                    "error": (
                        "result must equal the number of unique "
                        "correct_question_ids."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if temp_exam.result is not None and temp_exam.result != result_score:
            return Response(
                {"error": "Temp exam results have already been submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_count = temp_exam.student_bank_items.filter(
            student=student,
            question_id__in=correct_question_ids,
            is_solved_now=False,
        ).update(is_solved_now=True)

        if temp_exam.result is None:
            temp_exam.result = result_score
            temp_exam.save(update_fields=['result'])

        return Response({
            "message": "Temp exam results submitted successfully",
            "temp_exam_id": temp_exam.id,
            "result": temp_exam.result,
            "updated_questions": updated_count,
        }, status=status.HTTP_200_OK)
