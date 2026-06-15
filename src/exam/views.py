# RestFrameWork lib
import random
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework import generics
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q, Case, When, BooleanField, Sum, Subquery, OuterRef, IntegerField, Min, Max
from django.db.models.functions import Coalesce
from django.db import transaction
from core.permissions import HasValidAPIKey
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db.models import Prefetch, prefetch_related_objects
import logging
# custom filters
from exam.filters import RelatedCourseFilterBackend
# celery is optional in this project; copied code only needs the decorator shape.
try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        def decorator(inner):
            return inner
        return decorator(func) if func else decorator
# Models
from .serializers import QuestionSerializerWithCorrectAnswer, QuestionSerializerWithoutCorrectAnswer, StudentBankSerializer, StudentExamResultSerializer, AdminQuestionBankSerializer, StudentCreatedExamSerializer
from .models import AddReasonChoices, Answer, EssaySubmission, Exam, ExamModel, ExamModelQuestion, ExamQuestion, ExamType, Question, QuestionType, Result, ResultTrial, StudentBank, Submission, TempExam, TempExamAllowedTimes, AdminQuestionBank, StudentCreatedExam
from course.models import Course, Unit
from subscription.models import CourseSubscription
from subscription.access import student_has_course_access


def _question_explanation_fields(question, prefix="question_explanation"):
    if not question:
        return {
            f"{prefix}_text": None,
            f"{prefix}_video_url": None,
            f"{prefix}_recorded_audio": None,
        }
    return {
        f"{prefix}_text": question.explanation_text,
        f"{prefix}_video_url": question.explanation_video_url,
        f"{prefix}_recorded_audio": question.explanation_recorded_audio.url if question.explanation_recorded_audio else None,
    }


class CheckExamStartAbility(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, exam_id):
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id)

        exam_status = exam.status()
        if exam_status != "active":
            return Response(
                {"status": exam_status},
                status=status.HTTP_200_OK
            )

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
                        "exam_model_id": unsubmitted_trial.exam_model.id if unsubmitted_trial.exam_model else None
                    }
                }, status=status.HTTP_200_OK)

            if result.is_trials_finished:
                return Response(
                    {"status": "trials_finished", "status_message": "انتهت جميع المحاولات"},
                    status=status.HTTP_200_OK
                )

        except Result.DoesNotExist:
            pass

        return Response(
            {"status": "can_start", "status_message": "يمكنك البدء"},
            status=status.HTTP_200_OK
        )

class StartExam(APIView):
    permission_classes = [IsAuthenticated]

    def _has_active_subscription(self, student, course):
        return student_has_course_access(student, course)

    def _get_exam_questions(self, exam, result):
        if exam.type == ExamType.RANDOM:
            return self._get_random_exam_questions(exam, result)
        else:
            return self._get_manual_exam_questions(exam)

    def _get_random_exam_questions(self, exam, result):
        exam_models = ExamModel.objects.filter(exam=exam, is_active=True)
        if not exam_models.exists():
            return None, None

        exam_model = exam_models.order_by('?').first()
        result.exam_model = exam_model
        result.save()

        questions = list(
            ExamModelQuestion.objects
            .filter(exam_model=exam_model, is_active=True)
            .select_related("question")
            .prefetch_related("question__answers", "question__years")
        )
        questions = [mq.question for mq in questions]
        if exam.show_questions_in_random:
            random.shuffle(questions)  # Shuffle the questions
        return questions, exam_model

    def _get_manual_exam_questions(self, exam):
        questions = list(
            ExamQuestion.objects
            .filter(exam=exam, question__is_active=True)
            .select_related("question")
            .prefetch_related("question__answers", "question__years")
        )
        questions = [eq.question for eq in questions]
        if exam.show_questions_in_random:
            random.shuffle(questions)  # Shuffle the questions
        return questions, None

    def get(self, request, exam_id: int) -> Response:
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id)
        course = get_object_or_404(Course, id=exam.get_related_course())

        if not self._has_active_subscription(student, course):
            return Response(
                {"error": "You do not have access permissions"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Ensure the exam is active
        exam_status = exam.status()
        if exam_status != "active":
            return Response(
                {"error": f"Exam is {exam_status}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create Result
        result, created = Result.objects.get_or_create(
            student=student,
            exam=exam,
            defaults={'trial': 0}
        )

        # Check if trials are finished
        if not created and result.is_trials_finished:
            return Response(
                {"error": "You have finished your allowed trials for this exam"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check for an unsubmitted trial
        unsubmitted_trial = result.trials.filter(student_submitted_exam_at__isnull=True).order_by('-trial').first()

        if unsubmitted_trial:
            # Use the existing unsubmitted trial
            result_trial = unsubmitted_trial
            questions, exam_model = self._get_exam_questions(exam, result)
            if questions is None:
                return Response(
                    {"error": "No models available for this random exam"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if exam_model and not result_trial.exam_model:
                result_trial.exam_model = exam_model
                result_trial.save()

            # Serialize questions
            question_data = [QuestionSerializerWithoutCorrectAnswer(q).data for q in questions]

            return Response(
                {
                    "exam_id": exam.id,
                    "exam_title": exam.title,
                    "exam_time_limit": exam.time_limit,
                    "questions": question_data,
                    "exam_model": {
                        "id": exam_model.id,
                        "title": exam_model.title
                    } if exam_model else None,
                    "resuming": True,
                    "trial_id": result_trial.id,
                    "started_at": result_trial.student_started_exam_at
                },
                status=status.HTTP_200_OK
            )
        else:
            # Fetch questions before consuming a trial so misconfigured random
            # exams do not create an unusable attempt.
            questions, exam_model = self._get_exam_questions(exam, result)
            if questions is None:
                return Response(
                    {"error": "No models available for this random exam"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Increment trial counter
            result.trial += 1
            result.save()

            # Create a new ResultTrial for the current trial
            result_trial = ResultTrial.objects.create(
                result=result,
                trial=result.trial,
                student_started_exam_at=timezone.now()
            )

            if exam_model:
                result_trial.exam_model = exam_model
                result_trial.save()

            # Serialize questions
            question_data = [QuestionSerializerWithoutCorrectAnswer(q).data for q in questions]

            return Response(
                {
                    "exam_id": exam.id,
                    "exam_title": exam.title,
                    "exam_time_limit": exam.time_limit,
                    "questions": question_data,
                    "exam_model": {
                        "id": exam_model.id,
                        "title": exam_model.title
                    } if exam_model else None,
                    "resuming": False,
                    "trial_id": result_trial.id
                },
                status=status.HTTP_200_OK
            )

class SubmitExam(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @transaction.atomic
    def post(self, request, exam_id):
        student = request.user.student
        exam = get_object_or_404(Exam, pk=exam_id)
        submit_type = request.data.get("submit_type", "student_submit")
        
        # Add idempotency key to prevent duplicate submissions from network retries
        idempotency_key = request.META.get('HTTP_X_IDEMPOTENCY_KEY')
        if not idempotency_key:
            # Generate a unique key based on request content if not provided
            import hashlib
            content_hash = hashlib.md5(str(sorted(request.data.items())).encode()).hexdigest()
            idempotency_key = f"{student.id}_{exam_id}_{content_hash}"

        # Get all unique question IDs from the request
        question_ids = set()
        for key in request.data.keys():
            if key.startswith('question_id_'):
                question_ids.add(int(key.split('_')[-1]))
            elif key == 'question_id':  # Handle case where it's not numbered
                question_ids.add(int(request.data[key]))

        # Check for empty payload (no questions submitted)
        if not question_ids:
            return Response(
                {"error": "يرجى إرسال إجابات للأسئلة"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create Result and ResultTrial with select_for_update to prevent race conditions
        try:
            result = get_object_or_404(Result.objects.select_for_update(), student=student, exam=exam)
            result_trial = result.trials.select_for_update().filter(trial=result.trial).first()
            if not result_trial:
                return Response(
                    {"error": "لم يتم العثور على محاولة نشطة لهذا الامتحان"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error retrieving result/trial for student {student.id}, exam {exam_id}: {str(e)}")
            return Response(
                {"error": "تعذر استرداد جلسة الامتحان"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
        for question_id in question_ids:
            question = get_object_or_404(Question, pk=question_id)
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
                    StudentBank.objects.get_or_create(
                        student=student,
                        question=question,
                        defaults={"add_reason": AddReasonChoices.UNSOLVED}
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

                        StudentBank.objects.get_or_create(
                            student=student,
                            question=question,
                            defaults={"add_reason": AddReasonChoices.INCORRECT}
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
                    StudentBank.objects.get_or_create(
                        student=student,
                        question=question,
                        defaults={"add_reason": AddReasonChoices.UNSOLVED}
                    )
            elif question.question_type == QuestionType.ESSAY:
                # Process Essay answer
                essay_answer_text = request.data.get(f"essay_answer_text_{question_id}", "")
                # Handle file upload
                essay_answer_file = request.FILES.get(f"essay_file_{question_id}")
                # Update or create essay submission
                essay_submission, created = EssaySubmission.objects.update_or_create(
                    student=student,
                    exam=exam,
                    question=question,
                    result_trial=result_trial,
                    defaults={
                        'answer_text': essay_answer_text,
                        'answer_file': essay_answer_file,
                        'is_scored': False,
                        'score': None
                    }
                )

        # Calculate scores
        try:
            # Calculate MCQ score
            mcq_score = Submission.objects.filter(
                result_trial=result_trial,
                is_correct=True
            ).aggregate(total=Sum('question__points'))['total'] or 0

            # Calculate essay score (only scored essays)
            essay_score = EssaySubmission.objects.filter(
                result_trial=result_trial,
                is_scored=True
            ).aggregate(total=Sum('score'))['total'] or 0

            total_score = mcq_score + essay_score

            # Get exam total score
            if result.exam.type == ExamType.RANDOM and result_trial.exam_model:
                exam_score = ExamModelQuestion.objects.filter(
                    exam_model=result_trial.exam_model
                ).aggregate(total=Sum('question__points'))['total'] or 0
            else:
                exam_score = Question.objects.filter(
                    exam_questions__exam=result.exam,
                    is_active=True
                ).aggregate(total=Sum('points'))['total'] or 0

            # Update trial and result
            result_trial.score = total_score
            result_trial.exam_score = exam_score
            result_trial.student_submitted_exam_at = timezone.now()
            result_trial.submit_type = submit_type
            result_trial.save()

            result.score = total_score
            result.save()

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
            "is_succeeded": total_score >= (exam.passing_percent / 100) * result_trial.exam_score,
            "trial": result.trial
        }, status=status.HTTP_200_OK)


class StudentExamResultsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentExamResultSerializer
    filter_backends = [DjangoFilterBackend, RelatedCourseFilterBackend]
    filterset_fields = ['exam__course', 'exam__unit', 'exam__related_to']

    def get_queryset(self):
        student = self.request.user.student
        now = timezone.now()

        return Result.objects.filter(student=student).select_related(
            'exam', 
            'exam__course',
            'exam__unit',
            'student',
            'student__user',
            'exam_model'
        ).prefetch_related(
            Prefetch(
                'trials',
                queryset=ResultTrial.objects.order_by('-trial')
                    .select_related('exam_model')
            ),
            Prefetch(
                'exam__exam_questions',
                queryset=ExamQuestion.objects.select_related('question')
                    .filter(question__is_active=True)
            ),
            # Prefetch(  # Commented out as not needed
            #     'exam__submissions',
            #     queryset=Submission.objects.filter(student=student)
            #         .select_related('question', 'selected_answer', 'result_trial')
            # ),
            Prefetch(
                'exam_model__model_questions',
                queryset=ExamModelQuestion.objects.all(),
                to_attr='prefetched_model_questions'
            )
        ).order_by('-added')


class GetMyExamResult(APIView):
    permission_classes = [IsAuthenticated]

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

        # Fetch Essay submissions
        essay_submissions = EssaySubmission.objects.filter(
            student=student, exam=exam, result_trial=active_trial
        ).select_related('question', 'question__category')

        # Calculate counts
        correct_mcq_count = mcq_submissions.filter(is_correct=True).count()
        incorrect_mcq_count = mcq_submissions.filter(is_correct=False, is_solved=True).count()
        unsolved_mcq_count = mcq_submissions.filter(is_solved=False).count()
        correct_essay_count = essay_submissions.filter(is_scored=True, score__gt=0).count()
        incorrect_essay_count = essay_submissions.filter(is_scored=True, score=0).count()
        unscored_essay_count = essay_submissions.filter(is_scored=False).count()

        student_answers = []
        unsolved_questions = []
        unscored_essay_questions = []

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
                "question_image": question.image.url if question and question.image else None,
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ] if question else [],
                **_question_explanation_fields(question),
                "selected_answer": selected_answer_obj,  # Updated to include full object
                "is_correct": submission.is_correct if submission.is_correct is not None else False,
                "is_solved": submission.is_solved if submission.is_solved is not None else False,
                "points": question.points,
                "answers": answer_details  # Include all answers here
            }
            student_answers.append(answer_data)

            # if not submission.is_solved:
            #     unsolved_questions.append(answer_data)

        # Process Essay submissions
        for submission in essay_submissions:
            question = submission.question
            answer_data = {
                "submission_id": submission.id,
                "type": "essay",
                "question_id": question.id if question else None,
                "question_category": question.category.title if question and question.category else None,
                "question_category_id": question.category.id if question and question.category else None,
                "question_text": question.text if question else None,
                "question_image": question.image.url if question and question.image else None,
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ] if question else [],
                **_question_explanation_fields(question),
                "answer_text": submission.answer_text,
                "answer_file": submission.answer_file.url if submission.answer_file else None,
                "score": submission.score,
                "is_scored": submission.is_scored,
                "points": question.points,
            }
            student_answers.append(answer_data)

        # Fetch correct answers (can be kept for a separate summary if needed)
        questions = Question.objects.filter(exam_questions__exam=exam).distinct()
        correct_answers_summary = [
            {
                "question_id": question.id,
                "question_text": question.text,
                "question_image": question.image.url if question.image else None,
                "question_type": question.question_type,
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ],
                **_question_explanation_fields(question),
                "correct_answers": [
                    {"text": answer.text, "image": answer.image.url if answer.image else None}
                    for answer in question.answers.filter(is_correct=True)
                ],
            }
            for question in questions
        ]

        # Response payload
        response_data = {
            "active_trial": active_trial.id,
            "trial_number": active_trial.trial,
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_description": exam.description,
            "exam_score": active_trial.exam_score if active_trial else 0,
            "student_score": active_trial.score if active_trial else 0,
            "is_succeeded": result.is_succeeded,
            "student_trials": result.trial,
            "is_trials_finished": result.is_trials_finished,
            # Counts
            "number_of_essay": essay_submissions.count(),
            "number_of_mcq": mcq_submissions.count(),
            "correct_mcq_count": correct_mcq_count,
            "incorrect_mcq_count": incorrect_mcq_count,
            "unsolved_mcq_count": unsolved_mcq_count,
            "correct_essay_count": correct_essay_count,
            "incorrect_essay_count": incorrect_essay_count,
            "unscored_essay_count": unscored_essay_count,
            # Other data
            "student_answers": student_answers,
            # "unsolved_questions": unsolved_questions,
            # "unscored_essay_questions": unscored_essay_questions,
            # "correct_answers_summary": correct_answers_summary, # Renamed for clarity
            "student_started_exam_at": active_trial.student_started_exam_at if active_trial else None,
            "student_submitted_exam_at": active_trial.student_submitted_exam_at if active_trial else None,
            "submit_type": active_trial.submit_type if active_trial else None,
        }

        return Response(response_data, status=status.HTTP_200_OK)


class GetMyExamResultForTrial(APIView):
    permission_classes = [IsAuthenticated]

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


        # Fetch Essay submissions
        essay_submissions = EssaySubmission.objects.filter(
            student=student, exam=exam, result_trial=trial
        ).select_related('question', 'question__category')

        # Calculate counts
        correct_mcq_count = mcq_submissions.filter(is_correct=True).count()
        incorrect_mcq_count = mcq_submissions.filter(is_correct=False, is_solved=True).count()
        unsolved_mcq_count = mcq_submissions.filter(is_solved=False).count()
        correct_essay_count = essay_submissions.filter(is_scored=True, score__gt=0).count()
        incorrect_essay_count = essay_submissions.filter(is_scored=True, score=0).count()
        unscored_essay_count = essay_submissions.filter(is_scored=False).count()

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
                "question_image": question.image.url if question and question.image else None,
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ] if question else [],
                **_question_explanation_fields(question),
                "selected_answer": selected_answer_obj,
                "is_correct": submission.is_correct if submission.is_correct is not None else False,
                "is_solved": submission.is_solved if submission.is_solved is not None else False,
                "points": question.points,
                "answers": answer_details
            }
            student_answers.append(answer_data)

        # Process Essay submissions
        for submission in essay_submissions:
            question = submission.question
            answer_data = {
                "submission_id": submission.id,
                "type": "essay",
                "question_id": question.id if question else None,
                "question_category": question.category.title if question and question.category else None,
                "question_category_id": question.category.id if question and question.category else None,
                "question_text": question.text if question else None,
                "question_image": question.image.url if question and question.image else None,
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ] if question else [],
                **_question_explanation_fields(question),
                "answer_text": submission.answer_text,
                "answer_file": submission.answer_file.url if submission.answer_file else None,
                "score": submission.score,
                "is_scored": submission.is_scored,
                "points": question.points,
            }
            student_answers.append(answer_data)

        # Fetch correct answers (can be kept for a separate summary if needed)
        questions = Question.objects.filter(exam_questions__exam=exam).distinct()
        correct_answers_summary = [
            {
                "question_id": question.id,
                "question_text": question.text,
                "question_image": question.image.url if question.image else None,
                "question_type": question.question_type,
                "question_comment": question.comment,
                "question_years": [
                    {"id": y.id, "value": y.value} for y in question.years.all()
                ],
                **_question_explanation_fields(question),
                "correct_answers": [
                    {"text": answer.text, "image": answer.image.url if answer.image else None}
                    for answer in question.answers.filter(is_correct=True)
                ],
            }
            for question in questions
        ]

        # Determine if the student succeeded in this trial
        is_succeeded = False
        if trial.exam_score and trial.score is not None:
            is_succeeded = trial.score >= (exam.passing_percent / 100) * trial.exam_score

        # Response payload
        response_data = {
            "active_trial": trial.id,
            "trial_number": trial.trial,
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_description": exam.description,
            "exam_score": trial.exam_score if trial else 0,
            "student_score": trial.score if trial else 0,
            "is_succeeded": is_succeeded,
            "student_trials": trial.result.trial if trial else 0,
            "is_trials_finished": trial.result.is_trials_finished if trial else False,
            # Counts
            "number_of_essay": essay_submissions.count(),
            "number_of_mcq": mcq_submissions.count(),
            "correct_mcq_count": correct_mcq_count,
            "incorrect_mcq_count": incorrect_mcq_count,
            "unsolved_mcq_count": unsolved_mcq_count,
            "correct_essay_count": correct_essay_count,
            "incorrect_essay_count": incorrect_essay_count,
            "unscored_essay_count": unscored_essay_count,
            # Other data
            "student_answers": student_answers,
            "student_started_exam_at": trial.student_started_exam_at if trial else None,
            "student_submitted_exam_at": trial.student_submitted_exam_at if trial else None,
            "submit_type": trial.submit_type if trial else None,
            
        }

        return Response(response_data, status=status.HTTP_200_OK)


#^-------------------------------- {Student Temp Exams} ---------------------------------#

class StudentBankListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentBankSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['add_reason', 'is_solved_now', 'question__question_type']
    search_fields = ['question__text']

    def get_queryset(self):
        student = self.request.user.student
        
        # Optimized base queryset with selective field loading and proper joins
        queryset = StudentBank.objects.filter(student=student).select_related(
            'question',
            'question__course',
            'question__unit', 
            'question__category'
        ).only(
            # StudentBank fields
            'id', 'add_reason', 'is_solved_now', 'created',
            # Question fields (minimal needed for serialization)
            'question__id', 'question__text', 'question__explanation_text',
            'question__explanation_video_url', 'question__explanation_recorded_audio', 'question__points',
            'question__question_type', 'question__image',
            # Related fields for filtering
            'question__course__id', 'question__course__name',
            'question__unit__id', 'question__unit__name',
            'question__category__id', 'question__category__title'
        )
        
        # Apply filters efficiently using indexed fields
        course = self.request.query_params.get('course')
        unit = self.request.query_params.get('unit')

        if course:
            queryset = queryset.filter(question__course_id=course)
        if unit:
            queryset = queryset.filter(question__unit__id=unit)

        # Use indexed ordering
        return queryset.order_by('-created')

class CreateTempExam(APIView):
    permission_classes = [IsAuthenticated]

    def _sample_student_banks(self, base_queryset, k, exclude_ids=None):
        """Efficiently sample ~k StudentBank rows using optimized ID-range probing.
        Returns a list of StudentBank with question and filtered similar_questions prefetched.
        """
        qs = base_queryset
        if exclude_ids:
            qs = qs.exclude(id__in=exclude_ids)
        
        # Fast aggregation using indexes
        agg = qs.aggregate(min_id=Min('id'), max_id=Max('id'), total_count=Count('id'))
        min_id, max_id, total_count = agg.get('min_id'), agg.get('max_id'), agg.get('total_count', 0)
        
        if min_id is None or max_id is None or total_count == 0:
            return []

        chosen_ids = set()
        
        # Optimized sampling strategy based on dataset size
        if total_count <= k * 2:
            # For small datasets, just get all IDs efficiently
            all_ids = list(qs.values_list('id', flat=True))
            if len(all_ids) <= k:
                chosen_ids = set(all_ids)
            else:
                chosen_ids = set(random.sample(all_ids, k))
        else:
            # For large datasets, use ID-range probing with optimized attempts
            attempts = 0
            max_attempts = min(k * 3, 100)  # Reduced attempts for better performance
            
            while len(chosen_ids) < k and attempts < max_attempts:
                r = random.randint(min_id, max_id)
                # Single query to find candidate
                candidate = qs.filter(id__gte=r).values_list('id', flat=True).first()
                if candidate is None and r > min_id:
                    candidate = qs.filter(id__lt=r).order_by('-id').values_list('id', flat=True).first()
                if candidate is not None:
                    chosen_ids.add(candidate)
                attempts += 1

        if not chosen_ids:
            return []

        # Optimized bulk fetch with minimal fields and proper prefetching
        return list(
            StudentBank.objects.filter(id__in=chosen_ids)
            .select_related('question')
            .prefetch_related(
                Prefetch(
                    'question__similar_questions',
                    queryset=Question.objects.filter(
                        is_active=True, 
                        question_type=QuestionType.MCQ
                    ).only('id', 'text', 'explanation_text', 'explanation_video_url', 'explanation_recorded_audio', 'points', 'image', 'comment', 'difficulty')
                )
            )
            .only('id', 'student_id', 'question_id', 'is_solved_now')
        )

    def _get_similar_questions_for_temp_exam(self, student_bank_questions):
        """
        Optimized similar question selection with reduced database complexity.
        Returns a list of Question objects with no duplicates.
        """
        if not student_bank_questions:
            return []
            
        selected_questions = []
        used_question_ids = set()

        # Cache for similar questions to avoid repeated DB hits
        similar_questions_cache = {}
        
        for student_bank in student_bank_questions:
            original_question = student_bank.question
            original_id = original_question.id

            # Try to get a similar question
            selected_question = None
            
            # Check cache first
            if original_id not in similar_questions_cache:
                # Prefetch similar questions efficiently
                try:
                    similars = list(original_question.similar_questions.filter(
                        is_active=True, 
                        question_type=QuestionType.MCQ
                    ).only('id', 'text', 'explanation_text', 'explanation_video_url', 'explanation_recorded_audio', 'points', 'image', 'comment', 'difficulty')[:10])  # Limit to first 10
                    similar_questions_cache[original_id] = similars
                except Exception:
                    similar_questions_cache[original_id] = []
            
            # Get available similar questions (not already used)
            available_similars = [
                q for q in similar_questions_cache[original_id] 
                if q.id not in used_question_ids
            ]
            
            # Select question: prefer similar, fallback to original
            if available_similars:
                selected_question = random.choice(available_similars)
            elif original_id not in used_question_ids:
                selected_question = original_question

            # Add to selection if valid
            if selected_question and selected_question.id not in used_question_ids:
                selected_questions.append(selected_question)
                used_question_ids.add(selected_question.id)

        return selected_questions

    def post(self, request):
        student = request.user.student
        number_of_questions = request.data.get('number_of_questions')
        course = request.data.get('course')
        unit = request.data.get('unit')
        time_limit = request.data.get('time_limit', 30)  # Default 30 minutes
        selected_questions_type = request.data.get('selected_questions_type')

        # Validate input
        try:
            number_of_questions = int(number_of_questions)
            if number_of_questions <= 0:
                return Response(
                    {"error": "يجب أن يكون عدد الأسئلة رقماً موجباً"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "عدد الأسئلة غير صالح"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate selected_questions_type
        if selected_questions_type not in ['solved', 'not_solved', None]:
            return Response(
                {"error": "نوع الأسئلة المحدد غير صالح. يجب أن يكون 'solved' أو 'not_solved' أو null"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optimized daily limit check using indexed fields
        today = timezone.now().date()
        limit, created = TempExamAllowedTimes.objects.get_or_create(
            id=1,
            defaults={'number_of_allowedtempexams_per_day': 3}
        )

        # Single query for count with indexed date field
        used_attempts = TempExam.objects.filter(
            student=student,
            created__date=today
        ).count()

        if used_attempts >= limit.number_of_allowedtempexams_per_day:
            return Response(
                {"error": f"已达到每日临时考试限制 ({limit.number_of_allowedtempexams_per_day} 次)"},
                status=status.HTTP_400_BAD_REQUEST
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

        # Chain filters efficiently to leverage composite indexes
        if course:
            queryset = queryset.filter(question__course_id=course)
        if unit:
            queryset = queryset.filter(question__unit__id=unit)

        # Fast count using optimized queryset
        total_available = queryset.count()
        if total_available < number_of_questions:
            return Response(
                {"error": f"Not enough questions available. Found {total_available}, required {number_of_questions}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optimized sampling with reduced complexity
        selected_student_banks = self._sample_student_banks(queryset, number_of_questions)

        # Efficient similar question selection
        selected_questions = self._get_similar_questions_for_temp_exam(selected_student_banks)
        selected_question_ids = {q.id for q in selected_questions}

        # Simplified top-up strategy with reduced iterations
        if len(selected_questions) < number_of_questions:
            need = number_of_questions - len(selected_questions)
            used_bank_ids = {sb.id for sb in selected_student_banks}
            
            # Single additional sampling attempt
            additional_banks = self._sample_student_banks(
                queryset, 
                min(need * 2, 50),  # Cap additional sampling
                exclude_ids=used_bank_ids
            )
            
            if additional_banks:
                additional_questions = self._get_similar_questions_for_temp_exam(additional_banks)
                for q in additional_questions:
                    if q.id not in selected_question_ids and len(selected_questions) < number_of_questions:
                        selected_questions.append(q)
                        selected_question_ids.add(q.id)

        # Final validation with clear error message
        if len(selected_questions) < number_of_questions:
            return Response(
                {"error": f"Could not generate enough unique questions. Generated {len(selected_questions)}, required {number_of_questions}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        related_objects = {}
        if course:
            related_objects['course'] = Course.objects.filter(id=course).only('id').first()
        if unit:
            related_objects['unit'] = Unit.objects.filter(id=unit).only('id').first()

        temp_exam = TempExam.objects.create(
            student=student,
            course=related_objects.get('course'),
            unit=related_objects.get('unit'),
            number_of_questions=number_of_questions,
            time_limit=time_limit,
            selected_questions_type=selected_questions_type
        )

        # Optimized answer loading with single bulk query
        final_questions = selected_questions[:number_of_questions]
        final_question_ids = [q.id for q in final_questions]
        
        # Single optimized query for all answers
        answers_dict = {}
        if final_question_ids:
            answers = Answer.objects.filter(
                question_id__in=final_question_ids
            ).select_related().only(
                'id', 'text', 'image', 'is_correct', 'question_id'
            ).order_by('question_id', 'id')
            
            # Group answers by question efficiently
            for answer in answers:
                if answer.question_id not in answers_dict:
                    answers_dict[answer.question_id] = []
                answers_dict[answer.question_id].append(answer)
        
        # Attach answers to questions for serialization
        for question in final_questions:
            question._prefetched_answers = answers_dict.get(question.id, [])
        
        # Serialize with optimized data
        question_data = [QuestionSerializerWithCorrectAnswer(q).data for q in final_questions]

        return Response({
            "temp_exam_id": temp_exam.id,
            "number_of_questions": temp_exam.number_of_questions,
            "time_limit": temp_exam.time_limit,
            "course": temp_exam.course.id if temp_exam.course else None,
            "unit": temp_exam.unit.id if temp_exam.unit else None,
            "selected_questions_type": temp_exam.selected_questions_type,
            "questions": question_data
        }, status=status.HTTP_201_CREATED)

class SubmitTempExamResults(APIView):
    permission_classes = [IsAuthenticated]

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

        # Optimized temp exam retrieval with minimal fields
        temp_exam = get_object_or_404(
            TempExam.objects.only('id', 'student_id', 'result'),
            id=temp_exam_id, 
            student=student
        )

        # Batch update for better performance - single query instead of multiple
        if correct_question_ids:
            updated_count = StudentBank.objects.filter(
                student=student,
                question__id__in=correct_question_ids,
                is_solved_now=False  # Only update if not already solved
            ).update(is_solved_now=True)
        
        # Optimized result update with validation
        if result is not None:
            try:
                result_float = float(result)
                if temp_exam.result != result_float:  # Only update if changed
                    temp_exam.result = result_float
                    temp_exam.save(update_fields=['result'])  # Save only specific field
            except (ValueError, TypeError):
                return Response(
                    {"error": "Invalid result format. Must be a number."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response({
            "message": "Temp exam results submitted successfully",
            "temp_exam_id": temp_exam.id,
            "result": temp_exam.result,
            "updated_questions": len(correct_question_ids) if correct_question_ids else 0
        }, status=status.HTTP_200_OK)


#^-------------------------------- {Student Created Exams} ---------------------------------^#


class AdminQuestionBankListView(generics.ListAPIView):
    """List view for admin question bank - for admin users only"""
    serializer_class = AdminQuestionBankSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['question__question_type', 'question__course', 'question__unit']
    search_fields = ['question__text']

    def get_queryset(self):
        return AdminQuestionBank.objects.select_related('question').order_by('-created')


class CreateStudentExam(APIView):
    permission_classes = [IsAuthenticated]

    def _sample_admin_questions(self, base_queryset, k, exclude_ids=None):
        """Efficiently sample ~k AdminQuestionBank rows using optimized ID-range probing.
        Returns a list of AdminQuestionBank with question prefetched.
        """
        qs = base_queryset
        if exclude_ids:
            qs = qs.exclude(id__in=exclude_ids)
        
        # Fast aggregation using indexes
        agg = qs.aggregate(min_id=Min('id'), max_id=Max('id'), total_count=Count('id'))
        min_id, max_id, total_count = agg.get('min_id'), agg.get('max_id'), agg.get('total_count', 0)
        
        if min_id is None or max_id is None or total_count == 0:
            return []

        chosen_ids = set()
        
        # Optimized sampling strategy based on dataset size
        if total_count <= k * 2:
            # For small datasets, just get all IDs efficiently
            all_ids = list(qs.values_list('id', flat=True))
            if len(all_ids) <= k:
                chosen_ids = set(all_ids)
            else:
                chosen_ids = set(random.sample(all_ids, k))
        else:
            # For large datasets, use ID-range probing with optimized attempts
            attempts = 0
            max_attempts = min(k * 3, 100)  # Reduced attempts for better performance
            
            while len(chosen_ids) < k and attempts < max_attempts:
                r = random.randint(min_id, max_id)
                # Single query to find candidate
                candidate = qs.filter(id__gte=r).values_list('id', flat=True).first()
                if candidate is None and r > min_id:
                    candidate = qs.filter(id__lt=r).order_by('-id').values_list('id', flat=True).first()
                if candidate is not None:
                    chosen_ids.add(candidate)
                attempts += 1

        if not chosen_ids:
            return []

        # Optimized bulk fetch with minimal fields and proper prefetching
        return list(
            AdminQuestionBank.objects.filter(id__in=chosen_ids)
            .select_related('question')
            .only('id', 'question_id')
        )

    def post(self, request):
        student = request.user.student
        number_of_mcq_questions = request.data.get('number_of_mcq_questions', 0)
        number_of_essay_questions = request.data.get('number_of_essay_questions', 0)
        course = request.data.get('course')
        unit = request.data.get('unit')
        time_limit = request.data.get('time_limit', 60)  # Default 60 minutes

        # Validate input
        try:
            number_of_mcq_questions = int(number_of_mcq_questions)
            number_of_essay_questions = int(number_of_essay_questions)
            time_limit = int(time_limit)
            
            if number_of_mcq_questions < 0 or number_of_essay_questions < 0:
                return Response(
                    {"error": "Number of questions must be non-negative"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if number_of_mcq_questions + number_of_essay_questions == 0:
                return Response(
                    {"error": "Total number of questions must be greater than 0"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid number format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check daily limit using the same limit as TempExam
        today = timezone.now().date()
        limit, created = TempExamAllowedTimes.objects.get_or_create(
            id=1,
            defaults={'number_of_allowedtempexams_per_day': 3}
        )
        
        # Count both temp exams and student created exams for the daily limit
        used_attempts = (
            TempExam.objects.filter(student=student, created__date=today).count() +
            StudentCreatedExam.objects.filter(student=student, created__date=today).count()
        )

        if used_attempts >= limit.number_of_allowedtempexams_per_day:
            return Response(
                {"error": f"Daily exam limit of {limit.number_of_allowedtempexams_per_day} reached"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build queryset for admin question bank with early filtering
        queryset = AdminQuestionBank.objects.filter(
            question__is_active=True
        ).select_related('question').only(
            'id', 'question_id',
            'question__id', 'question__question_type', 'question__is_active'
        )

        # Apply filters
        if course:
            queryset = queryset.filter(question__course_id=course)
        if unit:
            queryset = queryset.filter(question__unit__id=unit)

        # Check availability for MCQ questions
        mcq_queryset = queryset.filter(question__question_type=QuestionType.MCQ)
        mcq_available = mcq_queryset.count()
        
        if mcq_available < number_of_mcq_questions:
            return Response(
                {"error": f"Not enough MCQ questions available. Found {mcq_available}, required {number_of_mcq_questions}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check availability for Essay questions
        essay_queryset = queryset.filter(question__question_type=QuestionType.ESSAY)
        essay_available = essay_queryset.count()
        
        if essay_available < number_of_essay_questions:
            return Response(
                {"error": f"Not enough Essay questions available. Found {essay_available}, required {number_of_essay_questions}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Sample MCQ questions
        selected_mcq_banks = []
        if number_of_mcq_questions > 0:
            selected_mcq_banks = self._sample_admin_questions(mcq_queryset, number_of_mcq_questions)

        # Sample Essay questions
        selected_essay_banks = []
        if number_of_essay_questions > 0:
            selected_essay_banks = self._sample_admin_questions(essay_queryset, number_of_essay_questions)

        # Combine all selected questions
        all_selected_banks = selected_mcq_banks + selected_essay_banks
        
        if len(all_selected_banks) < (number_of_mcq_questions + number_of_essay_questions):
            return Response(
                {"error": f"Could not generate enough unique questions. Generated {len(all_selected_banks)}, required {number_of_mcq_questions + number_of_essay_questions}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get related objects
        course_obj = None
        unit_obj = None
        if course:
            course_obj = get_object_or_404(Course, id=course)
        if unit:
            unit_obj = get_object_or_404(Unit, id=unit)

        # Calculate total exam score
        total_score = sum(bank.question.points for bank in all_selected_banks)

        # Create student exam
        student_exam = StudentCreatedExam.objects.create(
            student=student,
            course=course_obj,
            unit=unit_obj,
            number_of_mcq_questions=number_of_mcq_questions,
            number_of_essay_questions=number_of_essay_questions,
            time_limit=time_limit,
            exam_score=total_score
        )

        # Prepare questions data for response - get questions with answers
        question_ids = [bank.question.id for bank in all_selected_banks]
        questions_with_answers = Question.objects.filter(
            id__in=question_ids
        ).prefetch_related('answers')

        # Shuffle questions to randomize order
        questions_list = list(questions_with_answers)
        random.shuffle(questions_list)

        # Serialize questions
        question_data = [QuestionSerializerWithCorrectAnswer(q).data for q in questions_list]

        return Response({
            "student_exam_id": student_exam.id,
            "number_of_mcq_questions": student_exam.number_of_mcq_questions,
            "number_of_essay_questions": student_exam.number_of_essay_questions,
            "time_limit": student_exam.time_limit,
            "exam_score": student_exam.exam_score,
            "course": student_exam.course.id if student_exam.course else None,
            "unit": student_exam.unit.id if student_exam.unit else None,
            "questions": question_data
        }, status=status.HTTP_201_CREATED)


class SubmitStudentExamResults(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student = request.user.student
        student_exam_id = request.data.get('student_exam_id')
        result = request.data.get('result')

        # Validate inputs early
        if not student_exam_id:
            return Response(
                {"error": "student_exam_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            student_exam_id = int(student_exam_id)
        except (TypeError, ValueError):
            return Response(
                {"error": "student_exam_id must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optimized student exam retrieval with minimal fields
        student_exam = get_object_or_404(
            StudentCreatedExam.objects.only('id', 'student_id', 'result', 'exam_score'),
            id=student_exam_id, 
            student=student
        )

        # Check if result already submitted
        if student_exam.result is not None:
            return Response(
                {"error": "Exam results already submitted"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optimized result update with validation
        if result is not None:
            try:
                result_float = float(result)
                if result_float < 0:
                    return Response(
                        {"error": "Result cannot be negative"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if result_float > student_exam.exam_score:
                    return Response(
                        {"error": f"Result cannot exceed exam score ({student_exam.exam_score})"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                student_exam.result = result_float
                student_exam.save(update_fields=['result'])  # Save only specific field
                
            except (ValueError, TypeError):
                return Response(
                    {"error": "Invalid result format. Must be a number."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {"error": "Result is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate percentage
        percentage = (student_exam.result / student_exam.exam_score * 100) if student_exam.exam_score > 0 else 0

        return Response({
            "message": "Student exam results submitted successfully",
            "student_exam_id": student_exam.id,
            "result": student_exam.result,
            "exam_score": student_exam.exam_score,
            "percentage": percentage
        }, status=status.HTTP_200_OK)


class StudentCreatedExamListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StudentCreatedExamSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['course', 'unit']
    search_fields = ['course__name', 'unit__name']

    def get_queryset(self):
        student = self.request.user.student
        return StudentCreatedExam.objects.filter(
            student=student
        ).select_related('course', 'unit').order_by('-created')

