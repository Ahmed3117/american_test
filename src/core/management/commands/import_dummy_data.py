"""
Management command to import dummy data from JSON file.
Usage: python manage.py import_dummy_data [--json-file=PATH]
"""
import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from accounts.models import User, UserDevice, OTP
from student.models import Student
from course.models import Course, Unit, File
from exam.models import (
    Question, Answer, QuestionCategory, Year, Exam, ExamQuestion,
    ExamModel, ExamModelQuestion, RandomExamBank
)
from subscription.models import Plan, PlanSubscription, CourseSubscription


class Command(BaseCommand):
    help = 'Import dummy data from JSON file for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json-file',
            type=str,
            default=None,
            help='Path to JSON file (default: dummy_data.json in project root)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing dummy data before importing'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        if not json_file:
            json_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'dummy_data.json'
            )

        if not os.path.exists(json_file):
            raise CommandError(f'JSON file not found: {json_file}')

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if options['clear']:
            self.stdout.write('Clearing existing dummy data...')
            self.clear_data()

        self.stdout.write('Importing dummy data...')

        with transaction.atomic():
            admin = self.create_admin(data.get('admin', {}))
            self.stdout.write(f'  Admin: {admin.username}')

            students = self.create_students(data.get('students', []))
            self.stdout.write(f'  Students: {len(students)} created')

            categories = self.create_categories(data.get('question_categories', []))
            self.stdout.write(f'  Question categories: {len(categories)} created')

            courses = self.create_courses(data.get('courses', []))
            self.stdout.write(f'  Courses: {len(courses)} created')

            questions = self.create_questions(data.get('questions', []), courses, categories)
            self.stdout.write(f'  Questions: {len(questions)} created')

            exams = self.create_exams(data.get('exams', []), courses, questions)
            self.stdout.write(f'  Exams: {len(exams)} created')

            plans = self.create_plans(data.get('plans', []))
            self.stdout.write(f'  Plans: {len(plans)} created')

            subscriptions = self.create_subscriptions(
                data.get('subscriptions', []), students, plans, courses
            )
            self.stdout.write(f'  Subscriptions: {len(subscriptions)} created')

        self.stdout.write(self.style.SUCCESS('Dummy data imported successfully!'))

    def clear_data(self):
        CourseSubscription.objects.all().delete()
        PlanSubscription.objects.all().delete()
        Plan.objects.all().delete()
        ExamQuestion.objects.all().delete()
        RandomExamBank.objects.all().delete()
        ExamModelQuestion.objects.all().delete()
        ExamModel.objects.all().delete()
        Exam.objects.all().delete()
        Answer.objects.all().delete()
        # Delete Year last so the M2M through table is cleared first
        # (deleting a year does not cascade to questions, but the
        # through table must be empty before we delete Question rows).
        Question.objects.all().delete()
        QuestionCategory.objects.all().delete()
        Year.objects.all().delete()
        Unit.objects.all().delete()
        Course.objects.all().delete()
        Student.objects.all().delete()
        User.objects.filter(is_staff=False).delete()

    def create_admin(self, admin_data):
        username = admin_data.get('username', 'admin')
        password = admin_data.get('password', 'AdminPass123')

        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                'email': admin_data.get('email', 'admin@example.com'),
                'name': admin_data.get('name', 'Admin'),
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            user.set_password(password)
            user.save()

        return user

    def create_students(self, students_data):
        students = []
        for i, student_data in enumerate(students_data):
            user, created = User.objects.update_or_create(
                username=student_data['username'],
                defaults={
                    'email': student_data.get('email', ''),
                    'name': student_data.get('name', f'Student {i+1}'),
                    'user_type': 'student',
                    'parent_phone': student_data.get('parent_phone', ''),
                    'government': student_data.get('government', ''),
                }
            )
            if created:
                user.set_password(student_data.get('password', 'StudentPass123'))
                user.save()

            student, _ = Student.objects.update_or_create(
                user=user,
                defaults={
                    'name': student_data.get('name', f'Student {i+1}'),
                    'parent_phone': student_data.get('parent_phone', ''),
                }
            )

            if student_data.get('device_id'):
                UserDevice.objects.update_or_create(
                    user=user,
                    device_id=student_data['device_id'],
                    defaults={
                        'device_token': f'dummy_token_{student_data["username"]}',
                        'logged_in_at': timezone.now(),
                        'last_used_at': timezone.now(),
                        'is_active': True,
                    }
                )

            students.append(student)

        return students

    def create_categories(self, categories_data):
        categories = []
        for cat_data in categories_data:
            cat, _ = QuestionCategory.objects.update_or_create(
                title=cat_data['title']
            )
            categories.append(cat)
        return categories

    def create_courses(self, courses_data):
        courses = []
        for course_data in courses_data:
            course, created = Course.objects.update_or_create(
                name=course_data['name'],
                defaults={
                    'description': course_data.get('description', ''),
                    'order': course_data.get('order', 1),
                    'is_active': course_data.get('is_active', True),
                }
            )
            courses.append(course)

            for i, unit_data in enumerate(course_data.get('units', [])):
                unit, _ = Unit.objects.update_or_create(
                    course=course,
                    name=unit_data['name'],
                    defaults={
                        'description': unit_data.get('description', ''),
                        'order': unit_data.get('order', i + 1),
                        'is_active': unit_data.get('is_active', True),
                    }
                )

        return courses

    def create_questions(self, questions_data, courses, categories):
        questions = []
        for q_data in questions_data:
            course = courses[q_data.get('course_index', 0)] if q_data.get('course_index') is not None else None
            unit = None
            if course and q_data.get('unit_index') is not None:
                units = list(course.units.all())
                if q_data['unit_index'] < len(units):
                    unit = units[q_data['unit_index']]

            category = None
            if q_data.get('category_index') is not None and q_data['category_index'] < len(categories):
                category = categories[q_data['category_index']]

            question, created = Question.objects.update_or_create(
                text=q_data['text'],
                course=course,
                unit=unit,
                defaults={
                    'points': q_data.get('points', 1),
                    'difficulty': q_data.get('difficulty', 'EASY'),
                    'question_type': q_data.get('question_type', 'MCQ'),
                    'category': category,
                    'explanation_text': q_data.get('explanation_text', q_data.get('explanation', '')),
                    'explanation_video_url': q_data.get('explanation_video_url'),
                    'is_active': True,
                }
            )

            # Attach years (list of integer values) — auto-create missing
            year_values = q_data.get('years') or []
            if year_values:
                year_objs = [Year.objects.get_or_create(value=str(v))[0] for v in year_values]
                question.years.set(year_objs)

            questions.append(question)

            if question.question_type == 'MCQ':
                for ans_data in q_data.get('answers', []):
                    Answer.objects.update_or_create(
                        question=question,
                        text=ans_data['text'],
                        defaults={
                            'is_correct': ans_data.get('is_correct', False),
                        }
                    )

        return questions

    def create_exams(self, exams_data, courses, questions):
        exams = []
        for exam_data in exams_data:
            course = courses[exam_data.get('course_index', 0)] if exam_data.get('course_index') is not None else None

            exam, created = Exam.objects.update_or_create(
                title=exam_data['title'],
                defaults={
                    'description': exam_data.get('description', ''),
                    'related_to': exam_data.get('related_to', 'COURSE'),
                    'course': course,
                    'unit': None,
                    'type': exam_data.get('type', 'MANUAL'),
                    'number_of_questions': exam_data.get('number_of_questions', 1),
                    'time_limit': exam_data.get('time_limit', 30),
                    'score': 0,
                    'passing_percent': exam_data.get('passing_percent', 50),
                    'number_of_allowed_trials': exam_data.get('number_of_allowed_trials', 1),
                    'easy_questions_count': exam_data.get('easy_questions_count', 0),
                    'medium_questions_count': exam_data.get('medium_questions_count', 0),
                    'hard_questions_count': exam_data.get('hard_questions_count', 0),
                    'show_answers_after_finish': exam_data.get('show_answers_after_finish', False),
                    'order': exam_data.get('order', 1),
                    'is_active': exam_data.get('is_active', True),
                    'allow_show_results_at': exam_data.get('start', timezone.now()),
                    'allow_show_answers_at': exam_data.get('end', timezone.now()),
                    'is_depends': exam_data.get('is_depends', False),
                    'show_questions_in_random': exam_data.get('show_questions_in_random', True),
                    'ponus': exam_data.get('ponus', 0),
                    'ponus_option': exam_data.get('ponus_option'),
                    'start': exam_data.get('start', timezone.now()),
                    'end': exam_data.get('end', timezone.now() + timezone.timedelta(days=365)),
                }
            )

            if exam.type == 'MANUAL' and exam_data.get('question_indices'):
                for i, q_idx in enumerate(exam_data['question_indices']):
                    if q_idx < len(questions):
                        ExamQuestion.objects.update_or_create(
                            exam=exam,
                            question=questions[q_idx],
                            defaults={'order': i + 1, 'is_active': True}
                        )
                exam.score = exam.calculate_score()
                exam.number_of_questions = exam.calculate_number_of_questions()
                exam.save()

            elif exam.type == 'RANDOM' and exam_data.get('bank_question_indices'):
                bank, _ = RandomExamBank.objects.update_or_create(exam=exam)
                for q_idx in exam_data['bank_question_indices']:
                    if q_idx < len(questions):
                        bank.questions.add(questions[q_idx])

            exams.append(exam)

        return exams

    def create_plans(self, plans_data):
        plans = []
        for plan_data in plans_data:
            plan, _ = Plan.objects.update_or_create(
                title=plan_data['title'],
                defaults={
                    'price': plan_data.get('price', '0.00'),
                    'start_day': plan_data.get('start_day', 1),
                    'start_month': plan_data.get('start_month', 1),
                    'end_day': plan_data.get('end_day', 31),
                    'end_month': plan_data.get('end_month', 12),
                    'number_of_allowed_courses_to_subscribe': plan_data.get('number_of_allowed_courses_to_subscribe', 1),
                    'is_active': plan_data.get('is_active', True),
                }
            )
            plans.append(plan)
        return plans

    def create_subscriptions(self, subscriptions_data, students, plans, courses):
        subscriptions = []
        for sub_data in subscriptions_data:
            student = students[sub_data.get('student_index', 0)] if sub_data.get('student_index') is not None else None
            plan = plans[sub_data.get('plan_index', 0)] if sub_data.get('plan_index') is not None else None

            if not student or not plan:
                continue

            subscription, created = PlanSubscription.objects.update_or_create(
                student=student,
                plan=plan,
                defaults={
                    'payment_status': sub_data.get('status', 'pending'),
                }
            )

            for c_idx in sub_data.get('course_indices', []):
                if c_idx < len(courses):
                    CourseSubscription.objects.update_or_create(
                        student=student,
                        course=courses[c_idx],
                        defaults={
                            'plan_subscription': subscription,
                            'active': True,
                        }
                    )

            if sub_data.get('status') == 'paid':
                subscription.mark_paid(status='manual')

            subscriptions.append(subscription)

        return subscriptions
