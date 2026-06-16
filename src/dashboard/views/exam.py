import json
import random

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import CustomPageNumberPagination
from exam.models import (
    AdminQuestionBank,
    Answer,
    DifficultyLevel,
    EssaySubmission,
    Exam,
    ExamModel,
    ExamModelQuestion,
    ExamQuestion,
    ExamType,
    Question,
    QuestionCategory,
    QuestionType,
    RandomExamBank,
    Result,
    ResultTrial,
    Submission,
    TempExamAllowedTimes,
    Year,
)
from student.models import Student
from subscription.models import CourseSubscription

from dashboard.serializers.exam.exam import (
    AdminQuestionBankSerializer,
    AddExamQuestionsSerializer,
    AnswerSerializer,
    CopyExamSerializer,
    EssaySubmissionSerializer,
    ExamModelSerializer,
    ExamQuestionReorderSerializer,
    ExamQuestionSerializer,
    ExamSerializer,
    FlattenedExamResultSerializer,
    FlattenedStudentResultSerializer,
    QuestionCategorySerializer,
    QuestionSerializer,
    RandomExamBankSerializer,
    ResultSerializer,
    ResultTrialSerializer,
    StudentDidNotTakeExamSerializer,
    TempExamAllowedTimesSerializer,
    YearSerializer,
)


STAFF_PERMISSIONS = [IsAuthenticated, IsAdminUser]


def _bool(value):
    if value is None:
        return None
    return str(value).lower() in {"true", "1", "yes"}


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


def _exam_course_filter(course_id):
    return Q(course_id=course_id)


def _question_course_filter(course_id):
    return Q(course_id=course_id)


def _answer_payload_from_request(request, prefix):
    return {
        "text": request.data.get(f"{prefix}[text]"),
        "is_correct": str(request.data.get(f"{prefix}[is_correct]", "")).lower() == "true",
        "image": request.FILES.get(f"{prefix}[image]"),
    }


def _has_indexed_answers(data):
    return any(str(key).startswith("answers[") and str(key).endswith("][text]") for key in data.keys())


def _strip_parser_artifacts(data):
    cleaned = data.copy()
    cleaned.pop("answers", None)
    for key in list(cleaned.keys()):
        if str(key).startswith("answers["):
            cleaned.pop(key, None)
    return cleaned


def _coerce_int_list(values):
    if not isinstance(values, list):
        return None, "Expected a list of question IDs."
    cleaned = []
    invalid = []
    for value in values:
        try:
            cleaned.append(int(value))
        except (TypeError, ValueError):
            invalid.append(value)
    if invalid:
        return None, f"Invalid question IDs: {invalid}"
    return cleaned, None


def _parse_year_id_list(value):
    """Normalize the `years` form field into a flat list of Year primary keys.

    Accepts, for a single field, any of:
      * a list (already parsed, e.g. repeated `years=1&years=2`),
      * a JSON-array string `"[1,4,2]"`,
      * a comma-separated string `"1,4,2"`.

    Returns the list of ints, or raises `ValueError` when something is not an int.
    """
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        raw_items = value
    else:
        text = str(value).strip()
        if text.startswith("["):
            try:
                raw_items = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON for years list: {exc.msg}") from exc
            if not isinstance(raw_items, list):
                raise ValueError("years must be a JSON array of integers")
        else:
            raw_items = [piece for piece in text.split(",") if piece.strip() != ""]
    ids = []
    for item in raw_items:
        try:
            ids.append(int(item))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Year id must be an integer, got {item!r}") from exc
    return ids


def _serialize_trial_answer(submission):
    question = submission.question
    answers = [
        {
            "id": answer.id,
            "text": answer.text,
            "image": answer.image.url if answer.image else None,
            "is_correct": answer.is_correct,
        }
        for answer in question.answers.all()
    ]
    selected_answer = None
    if submission.selected_answer:
        selected_answer = {
            "id": submission.selected_answer_id,
            "text": submission.selected_answer.text,
            "image": submission.selected_answer.image.url if submission.selected_answer.image else None,
            "is_correct": submission.selected_answer.is_correct,
        }
    return {
        "submission_id": submission.id,
        "type": "mcq",
        "question_id": question.id,
        "question_category": question.category.title if question.category else None,
        "question_category_id": question.category_id,
        "question_text": question.text,
        "question_image": question.image.url if question.image else None,
        "question_comment": question.comment,
        "question_years": [
            {"id": y.id, "value": y.value} for y in question.years.all()
        ],
        **_question_explanation_fields(question),
        "selected_answer": selected_answer,
        "is_correct": submission.is_correct,
        "is_solved": submission.is_solved,
        "points": question.points,
        "answers": answers,
    }


def _serialize_essay_submission(submission):
    question = submission.question
    return {
        "submission_id": submission.id,
        "type": "essay",
        "question_id": question.id,
        "question_category": question.category.title if question.category else None,
        "question_category_id": question.category_id,
        "question_text": question.text,
        "question_image": question.image.url if question.image else None,
        "question_comment": question.comment,
        "question_years": [
            {"id": y.id, "value": y.value} for y in question.years.all()
        ],
        **_question_explanation_fields(question),
        "answer_text": submission.answer_text,
        "answer_file": submission.answer_file.url if submission.answer_file else None,
        "score": submission.score,
        "is_scored": submission.is_scored,
        "points": question.points,
        "answers": [],
    }


def _result_detail_payload(result, trial):
    mcq_submissions = (
        Submission.objects.filter(result_trial=trial)
        .select_related("question", "selected_answer", "question__category")
        .prefetch_related("question__answers")
    )
    essay_submissions = EssaySubmission.objects.filter(result_trial=trial).select_related("question", "question__category")
    student_answers = [_serialize_trial_answer(item) for item in mcq_submissions]
    student_answers.extend(_serialize_essay_submission(item) for item in essay_submissions)

    is_succeeded = False
    if trial and trial.exam_score:
        is_succeeded = trial.score >= (result.exam.passing_percent / 100) * trial.exam_score

    return {
        "active_trial": trial.id if trial else None,
        "trial_number": trial.trial if trial else None,
        "student_id": result.student_id,
        "student_name": result.student.name,
        "exam_id": result.exam_id,
        "exam_title": result.exam.title,
        "exam_description": result.exam.description,
        "exam_score": trial.exam_score if trial else 0,
        "student_score": trial.score if trial else 0,
        "is_succeeded": is_succeeded,
        "student_trials": result.trial,
        "is_trials_finished": result.is_trials_finished,
        "number_of_essay": essay_submissions.count(),
        "number_of_mcq": mcq_submissions.count(),
        "correct_mcq_count": mcq_submissions.filter(is_correct=True).count(),
        "incorrect_mcq_count": mcq_submissions.filter(is_correct=False, is_solved=True).count(),
        "unsolved_mcq_count": mcq_submissions.filter(is_solved=False).count(),
        "correct_essay_count": essay_submissions.filter(is_scored=True, score__gt=0).count(),
        "incorrect_essay_count": essay_submissions.filter(is_scored=True, score=0).count(),
        "unscored_essay_count": essay_submissions.filter(is_scored=False).count(),
        "student_answers": student_answers,
        "trials": [
            {
                "trial_number": item.trial,
                "score": item.score,
                "exam_score": item.exam_score,
                "student_started_exam_at": item.student_started_exam_at,
                "student_submitted_exam_at": item.student_submitted_exam_at,
                "submit_type": item.submit_type,
                "trial_id": item.id,
                "is_active": trial and item.id == trial.id,
            }
            for item in result.trials.all().order_by("trial")
        ],
        "student_started_exam_at": trial.student_started_exam_at if trial else None,
        "student_submitted_exam_at": trial.student_submitted_exam_at if trial else None,
        "submit_type": trial.submit_type if trial else None,
    }


class ExamListCreateView(generics.ListCreateAPIView):
    queryset = Exam.objects.select_related("course", "unit").order_by("-created")
    serializer_class = ExamSerializer
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ["related_to", "is_active", "course", "unit", "type", "created", "start", "end", "allow_show_results_at"]
    search_fields = ["title", "description", "course__name", "unit__name"]
    ordering_fields = ["order", "start", "end", "created"]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            now = timezone.now()
            if status_filter == "soon":
                queryset = queryset.filter(start__gt=now)
            elif status_filter == "active":
                queryset = queryset.filter(start__lte=now, end__gte=now)
            elif status_filter == "finished":
                queryset = queryset.filter(end__lt=now)
        related_course = self.request.query_params.get("related_course")
        if related_course:
            queryset = queryset.filter(_exam_course_filter(related_course))
        return queryset

    def perform_create(self, serializer):
        exam = serializer.save()
        exam.full_clean()


class ExamDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Exam.objects.select_related("course", "unit")
    serializer_class = ExamSerializer
    permission_classes = STAFF_PERMISSIONS


class QuestionCategoryListCreateView(generics.ListCreateAPIView):
    queryset = QuestionCategory.objects.order_by("id")
    permission_classes = STAFF_PERMISSIONS
    serializer_class = QuestionCategorySerializer


class QuestionCategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = QuestionCategory.objects.all()
    permission_classes = STAFF_PERMISSIONS
    serializer_class = QuestionCategorySerializer


class YearListCreateView(generics.ListCreateAPIView):
    queryset = Year.objects.all()
    serializer_class = YearSerializer
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["value"]
    ordering_fields = ["value", "id"]
    ordering = ["-value"]


class YearRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Year.objects.all()
    serializer_class = YearSerializer
    permission_classes = STAFF_PERMISSIONS


class QuestionListCreateView(generics.ListCreateAPIView):
    queryset = (
        Question.objects
        .select_related("course", "unit", "category")
        .prefetch_related("answers", "years")
        .order_by("-created", "-id")
    )
    permission_classes = STAFF_PERMISSIONS
    serializer_class = QuestionSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = (DjangoFilterBackend, SearchFilter)
    filterset_fields = {
        "course": ["exact"],
        "unit": ["exact"],
        "is_active": ["exact"],
        "difficulty": ["exact"],
        "category": ["exact"],
        "question_type": ["exact"],
        "years": ["exact"],
    }
    search_fields = ["text", "answers__text"]

    def get_queryset(self):
        qs = super().get_queryset()
        # multi-year support: ?years=2022,2024,2025 (accepts ids OR values)
        years_param = self.request.query_params.get("years")
        if years_param:
            raw = [v.strip() for v in years_param.split(",") if v.strip()]
            value_ids = [v for v in raw if v]
            if value_ids:
                qs = qs.filter(years__value__in=value_ids).distinct()
        return qs

    def create(self, request, *args, **kwargs):
        if "answers" in request.data and not _has_indexed_answers(request.data):
            return super().create(request, *args, **kwargs)
        data = _strip_parser_artifacts(request.data)
        if "image" in request.FILES:
            data["image"] = request.FILES["image"]
        if "explanation_recorded_audio" in request.FILES:
            data["explanation_recorded_audio"] = request.FILES["explanation_recorded_audio"]
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save()

        index = 0
        while f"answers[{index}][text]" in request.data:
            payload = _answer_payload_from_request(request, f"answers[{index}]")
            payload["question"] = question.id
            answer_serializer = AnswerSerializer(data=payload)
            answer_serializer.is_valid(raise_exception=True)
            answer_serializer.save()
            index += 1
        return Response(self.get_serializer(question).data, status=status.HTTP_201_CREATED)


class QuestionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Question.objects.select_related("course", "unit", "category").prefetch_related("answers")
    serializer_class = QuestionSerializer
    permission_classes = STAFF_PERMISSIONS
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()

        if "answers" in request.data and not _has_indexed_answers(request.data):
            return super().patch(request, *args, **kwargs)

        data = _strip_parser_artifacts(request.data)
        if "image" in request.FILES:
            data["image"] = request.FILES["image"]
        if "explanation_recorded_audio" in request.FILES:
            data["explanation_recorded_audio"] = request.FILES["explanation_recorded_audio"]

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        processed_ids = []
        index = 0
        while f"answers[{index}][text]" in request.data:
            answer_id = request.data.get(f"answers[{index}][id]")
            payload = _answer_payload_from_request(request, f"answers[{index}]")
            payload["question"] = instance.id
            if answer_id:
                answer = get_object_or_404(Answer, id=answer_id, question=instance)
                answer_serializer = AnswerSerializer(answer, data=payload, partial=True)
                answer_serializer.is_valid(raise_exception=True)
                answer_serializer.save()
                processed_ids.append(int(answer_id))
            else:
                answer_serializer = AnswerSerializer(data=payload)
                answer_serializer.is_valid(raise_exception=True)
                saved = answer_serializer.save()
                processed_ids.append(saved.id)
            index += 1

        if processed_ids:
            instance.answers.exclude(id__in=processed_ids).delete()

        instance = self.get_object()
        return Response(self.get_serializer(instance).data)


class BulkQuestionCreateView(generics.CreateAPIView):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = STAFF_PERMISSIONS

    def create(self, request, *args, **kwargs):
        created_questions = []
        exam = None
        exam_id = request.data.get("exam_id")
        if exam_id:
            exam = get_object_or_404(Exam, id=exam_id)

        with transaction.atomic():
            index = 0
            while f"questions[{index}][text]" in request.data:
                data = {
                    "text": request.data.get(f"questions[{index}][text]"),
                    "points": request.data.get(f"questions[{index}][points]"),
                    "difficulty": request.data.get(f"questions[{index}][difficulty]"),
                    "category": request.data.get(f"questions[{index}][category]"),
                    "course": request.data.get(f"questions[{index}][course]"),
                    "unit": request.data.get(f"questions[{index}][unit]"),
                    "question_type": request.data.get(f"questions[{index}][question_type]"),
                    "comment": request.data.get(f"questions[{index}][comment]"),
                    "explanation_text": request.data.get(
                        f"questions[{index}][explanation_text]",
                        request.data.get(f"questions[{index}][explanation]"),
                    ),
                    "explanation_video_url": request.data.get(f"questions[{index}][explanation_video_url]"),
                }
                image_key = f"questions[{index}][image]"
                if image_key in request.FILES:
                    data["image"] = request.FILES[image_key]
                audio_key = f"questions[{index}][explanation_recorded_audio]"
                if audio_key in request.FILES:
                    data["explanation_recorded_audio"] = request.FILES[audio_key]
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                question = serializer.save()
                if exam:
                    ExamQuestion.objects.get_or_create(exam=exam, question=question)

                # Attach years (list of Year primary keys).
                # Accepts JSON-array string "[1,4,2]", comma-separated "1,4,2",
                # or repeated fields. Years are looked up by ID; an unknown ID
                # returns 400.
                years_raw = request.data.get(f"questions[{index}][years]")
                if years_raw not in (None, ""):
                    try:
                        year_ids = _parse_year_id_list(years_raw)
                    except ValueError as exc:
                        return Response(
                            {"error": str(exc), "field": f"questions[{index}][years]"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if year_ids:
                        existing = Year.objects.filter(id__in=year_ids)
                        missing = sorted(set(year_ids) - set(existing.values_list("id", flat=True)))
                        if missing:
                            return Response(
                                {
                                    "error": "سنة غير موجودة",
                                    "missing_year_ids": missing,
                                    "field": f"questions[{index}][years]",
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        question.years.set(existing)

                answer_index = 0
                while f"questions[{index}][answers][{answer_index}][text]" in request.data:
                    payload = _answer_payload_from_request(request, f"questions[{index}][answers][{answer_index}]")
                    payload["question"] = question.id
                    answer_serializer = AnswerSerializer(data=payload)
                    answer_serializer.is_valid(raise_exception=True)
                    answer_serializer.save()
                    answer_index += 1
                created_questions.append(question)
                index += 1

        data = self.get_serializer(created_questions, many=True).data
        return Response({"exam_id": exam.id, "questions": data} if exam else data, status=status.HTTP_201_CREATED)


class AnswerListCreateView(generics.ListCreateAPIView):
    queryset = Answer.objects.select_related("question").order_by("id")
    serializer_class = AnswerSerializer
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["question"]


class AnswerRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Answer.objects.select_related("question")
    serializer_class = AnswerSerializer
    permission_classes = STAFF_PERMISSIONS


class EssaySubmissionListView(generics.ListAPIView):
    queryset = EssaySubmission.objects.select_related("student", "student__user", "exam", "question", "result_trial").order_by("-created", "-id")
    permission_classes = STAFF_PERMISSIONS
    serializer_class = EssaySubmissionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["exam", "student", "student__user", "question", "result_trial", "is_scored"]
    search_fields = ["student__name", "exam__title"]


class ScoreEssayQuestion(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Question.objects.all()

    def post(self, request, submission_id):
        essay_submission = get_object_or_404(EssaySubmission, pk=submission_id)
        try:
            score = float(request.data.get("score"))
        except (TypeError, ValueError):
            return Response({"error": "صيغة الدرجة غير صالحة. يجب أن تكون رقماً"}, status=status.HTTP_400_BAD_REQUEST)
        if score < 0 or score > essay_submission.question.points:
            return Response({"error": f"يجب أن تكون الدرجة بين 0 و {essay_submission.question.points}"}, status=status.HTTP_400_BAD_REQUEST)

        essay_submission.score = score
        essay_submission.is_scored = True
        essay_submission.save(update_fields=["score", "is_scored"])
        result = get_object_or_404(Result, student=essay_submission.student, exam=essay_submission.exam)
        trial = essay_submission.result_trial
        if trial:
            mcq_score = Submission.objects.filter(result_trial=trial, is_correct=True).aggregate(total=Sum("question__points"))["total"] or 0
            essay_score = EssaySubmission.objects.filter(result_trial=trial, is_scored=True).aggregate(total=Sum("score"))["total"] or 0
            total_score = mcq_score + essay_score
            trial.score = total_score
            trial.save(update_fields=["score"])
            result.save()
        return Response({"message": "تم تقييم السؤال الإنشائي بنجاح", "submission": EssaySubmissionSerializer(essay_submission, context={"request": request}).data})


class QuestionCountView(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Question.objects.all()

    def get(self, request, *args, **kwargs):
        filters = Q()
        if request.query_params.get("is_active") is not None:
            filters &= Q(is_active=_bool(request.query_params.get("is_active")))
        if request.query_params.get("category"):
            filters &= Q(category_id=request.query_params["category"])
        if request.query_params.get("unit"):
            filters &= Q(unit_id=request.query_params["unit"])
        if request.query_params.get("course"):
            filters &= _question_course_filter(request.query_params["course"])
        if request.query_params.get("question_type"):
            filters &= Q(question_type=request.query_params["question_type"])

        queryset = Question.objects.filter(filters)
        return Response(
            {
                "count": queryset.count(),
                "active_count": queryset.filter(is_active=True).count(),
                "mcq_count": queryset.filter(question_type=QuestionType.MCQ).count(),
                "essay_count": queryset.filter(question_type=QuestionType.ESSAY).count(),
                "easy_count": queryset.filter(difficulty=DifficultyLevel.EASY).count(),
                "medium_count": queryset.filter(difficulty=DifficultyLevel.MEDIUM).count(),
                "hard_count": queryset.filter(difficulty=DifficultyLevel.HARD).count(),
            }
        )


class GetExamQuestions(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Exam.objects.all()

    def get(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        if exam.type == ExamType.RANDOM:
            return Response({"message": "هذا امتحان عشوائي، سأختار أسئلته عشوائياً"})
        exam_questions = ExamQuestion.objects.filter(exam=exam).select_related("question").order_by("order", "id")
        return Response({"exam_id": exam.id, "exam_title": exam.title, "questions": ExamQuestionSerializer(exam_questions, many=True).data})


class ExamQuestionListCreateView(APIView):
    permission_classes = STAFF_PERMISSIONS

    def get(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        serializer = ExamQuestionSerializer(exam.exam_questions.select_related("question").all(), many=True)
        return Response(serializer.data)

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        serializer = AddExamQuestionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = []

        next_order = (exam.exam_questions.order_by("-order").values_list("order", flat=True).first() or 0) + 1
        for question_id in serializer.validated_data["question_ids"]:
            exam_question, was_created = ExamQuestion.objects.get_or_create(
                exam=exam,
                question_id=question_id,
                defaults={"order": next_order},
            )
            if was_created:
                created.append(exam_question)
                next_order += 1

        exam.score = exam.calculate_score()
        exam.number_of_questions = exam.calculate_number_of_questions()
        exam.save(update_fields=["score", "number_of_questions"])
        return Response(ExamQuestionSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class ExamQuestionDetailView(APIView):
    permission_classes = STAFF_PERMISSIONS

    def delete(self, request, exam_id, question_id):
        exam_question = get_object_or_404(ExamQuestion, exam_id=exam_id, question_id=question_id)
        exam = exam_question.exam
        exam_question.delete()
        exam.score = exam.calculate_score()
        exam.number_of_questions = exam.calculate_number_of_questions()
        exam.save(update_fields=["score", "number_of_questions"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AddBankExamQuestionsView(APIView):
    permission_classes = STAFF_PERMISSIONS
    parser_classes = [JSONParser]
    queryset = Question.objects.all()

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        question_ids, error = _coerce_int_list(request.data.get("questions_ids", request.data.get("question_ids", [])))
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        questions = Question.objects.filter(id__in=question_ids)
        invalid_ids = set(question_ids) - set(questions.values_list("id", flat=True))
        if invalid_ids:
            return Response({"error": f"The following question IDs are invalid: {sorted(invalid_ids)}"}, status=status.HTTP_400_BAD_REQUEST)
        added, skipped = [], []
        next_order = (exam.exam_questions.order_by("-order").values_list("order", flat=True).first() or 0) + 1
        for question in questions:
            _, created = ExamQuestion.objects.get_or_create(exam=exam, question=question, defaults={"order": next_order})
            if created:
                added.append(question.id)
                next_order += 1
            else:
                skipped.append(question.id)
        exam.score = exam.calculate_score()
        exam.number_of_questions = exam.calculate_number_of_questions()
        exam.save(update_fields=["score", "number_of_questions"])
        return Response({"message": "تمت إضافة الأسئلة إلى الامتحان بنجاح", "exam_id": exam.id, "added_questions": added, "skipped_questions": skipped}, status=status.HTTP_201_CREATED)


class AddManualExamQuestionsView(APIView):
    permission_classes = STAFF_PERMISSIONS
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Question.objects.all()

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        data = _strip_parser_artifacts(request.data)
        if "image" in request.FILES:
            data["image"] = request.FILES["image"]
        if "explanation_recorded_audio" in request.FILES:
            data["explanation_recorded_audio"] = request.FILES["explanation_recorded_audio"]
        if "years" in data and data["years"] not in (None, ""):
            try:
                data["years"] = _parse_year_id_list(data["years"])
            except ValueError as exc:
                return Response(
                    {"error": str(exc), "field": "years"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer = QuestionSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        index = 0
        while f"answers[{index}][text]" in request.data:
            payload = _answer_payload_from_request(request, f"answers[{index}]")
            payload["question"] = question.id
            answer_serializer = AnswerSerializer(data=payload)
            answer_serializer.is_valid(raise_exception=True)
            answer_serializer.save()
            index += 1
        ExamQuestion.objects.get_or_create(exam=exam, question=question)
        return Response({"message": "تم إنشاء السؤال وإضافته إلى الامتحان بنجاح", "question": QuestionSerializer(question).data}, status=status.HTTP_201_CREATED)


class RemoveExamQuestion(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Question.objects.all()

    def delete(self, request, exam_id, question_id):
        exam_question = get_object_or_404(ExamQuestion, exam_id=exam_id, question_id=question_id)
        exam = exam_question.exam
        exam_question.delete()
        exam.score = exam.calculate_score()
        exam.number_of_questions = exam.calculate_number_of_questions()
        exam.save(update_fields=["score", "number_of_questions"])
        return Response({"message": "تم حذف السؤال من الامتحان"})


class GetRandomExamBank(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = ExamModel.objects.all()

    def get(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        if exam.type != ExamType.RANDOM:
            return Response({"error": "هذا المسار مخصص لامتحانات النوع العشوائي فقط"}, status=status.HTTP_400_BAD_REQUEST)
        bank = get_object_or_404(RandomExamBank, exam=exam)
        return Response(RandomExamBankSerializer(bank).data)


class AddToRandomExamBank(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = ExamModel.objects.all()

    def post(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        if exam.type != ExamType.RANDOM:
            return Response({"error": "هذا المسار مخصص لامتحانات النوع العشوائي فقط"}, status=status.HTTP_400_BAD_REQUEST)
        question_ids, error = _coerce_int_list(request.data.get("question_ids", []))
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        questions = Question.objects.filter(id__in=question_ids)
        if questions.count() != len(set(question_ids)):
            return Response({"error": "بعض معرفات الأسئلة غير صالحة"}, status=status.HTTP_400_BAD_REQUEST)
        bank, _ = RandomExamBank.objects.get_or_create(exam=exam)
        bank.questions.add(*questions)
        return Response({"message": "تمت إضافة الأسئلة إلى بنك الامتحان العشوائي"}, status=status.HTTP_201_CREATED)


class ExamModelListCreateView(generics.ListCreateAPIView):
    queryset = ExamModel.objects.select_related("exam")
    permission_classes = STAFF_PERMISSIONS
    serializer_class = ExamModelSerializer
    filterset_fields = ["is_active", "exam"]


class ExamModelRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ExamModel.objects.select_related("exam")
    permission_classes = STAFF_PERMISSIONS
    serializer_class = ExamModelSerializer


class GetExamModelQuestions(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = ExamModel.objects.all()

    def get(self, request, exam_model_id):
        model = get_object_or_404(ExamModel, pk=exam_model_id)
        questions = [item.question for item in model.model_questions.select_related("question").all()]
        return Response({"exam_model_id": model.id, "exam_model_title": model.title, "questions": QuestionSerializer(questions, many=True).data})


class RemoveQuestionFromExamModel(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = ExamModel.objects.all()

    def delete(self, request, exam_model_id, question_id):
        item = get_object_or_404(ExamModelQuestion, exam_model_id=exam_model_id, question_id=question_id)
        item.delete()
        return Response({"message": "تم حذف السؤال من نموذج الامتحان بنجاح"})


class SuggestQuestionsForModel(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = ExamModel.objects.all()

    def get(self, request, exam_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        if exam.type != ExamType.RANDOM:
            return Response({"error": "هذا المسار مخصص لامتحانات النوع العشوائي فقط"}, status=status.HTTP_400_BAD_REQUEST)
        bank = RandomExamBank.objects.filter(exam=exam).first()
        if not bank:
            return Response({"error": "لا يوجد بنك عشوائي متاح لهذا الامتحان، يرجى إنشاء واحد أولاً"}, status=status.HTTP_400_BAD_REQUEST)
        questions = bank.questions.filter(is_active=True)
        if questions.count() < exam.number_of_questions:
            return Response({"error": "لا تتوفر أسئلة كافية لهذا الامتحان"}, status=status.HTTP_400_BAD_REQUEST)
        selected = []
        if exam.easy_questions_count or exam.medium_questions_count or exam.hard_questions_count:
            for difficulty, count in [("EASY", exam.easy_questions_count), ("MEDIUM", exam.medium_questions_count), ("HARD", exam.hard_questions_count)]:
                if count:
                    selected.extend(questions.filter(difficulty=difficulty).order_by("?")[:count])
        else:
            selected = list(questions.order_by("?")[: exam.number_of_questions])
        return Response({"exam_id": exam.id, "exam_title": exam.title, "questions": QuestionSerializer(selected, many=True).data})


class AddQuestionsToModel(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = ExamModel.objects.all()

    def post(self, request, exam_id, exam_model_id):
        exam = get_object_or_404(Exam, pk=exam_id)
        model = get_object_or_404(ExamModel, pk=exam_model_id, exam=exam)
        question_ids, error = _coerce_int_list(request.data.get("question_ids", []))
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        questions = Question.objects.filter(id__in=question_ids)
        invalid_ids = set(question_ids) - set(questions.values_list("id", flat=True))
        if invalid_ids:
            return Response({"error": f"معرفات الأسئلة التالية غير صالحة: {sorted(invalid_ids)}"}, status=status.HTTP_400_BAD_REQUEST)
        added, skipped = [], []
        for question in questions:
            _, created = ExamModelQuestion.objects.get_or_create(exam_model=model, question=question)
            (added if created else skipped).append(question.id)
        return Response({"message": "تمت إضافة الأسئلة إلى نموذج الامتحان بنجاح", "model_id": model.id, "added_questions": added, "skipped_questions": skipped}, status=status.HTTP_201_CREATED)


class ResultListView(generics.ListAPIView):
    serializer_class = ResultSerializer
    pagination_class = CustomPageNumberPagination
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"student": ["exact"], "exam": ["exact"], "exam__course": ["exact"], "exam__unit": ["exact"], "exam__related_to": ["exact"]}
    search_fields = ["student__name", "student__user__username", "exam__title", "exam__description"]
    ordering_fields = ["added", "trial"]
    ordering = ["-added"]

    def get_queryset(self):
        queryset = Result.objects.select_related("student", "student__user", "exam", "exam__course", "exam__unit").prefetch_related("trials")
        submitted = self.request.query_params.get("submitted")
        if submitted is not None:
            if _bool(submitted):
                queryset = queryset.filter(trials__student_submitted_exam_at__isnull=False).distinct()
            else:
                queryset = queryset.filter(trials__student_submitted_exam_at__isnull=True).distinct()
        return queryset


class ReduceResultTrialView(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Exam.objects.all()

    def post(self, request, result_id):
        result = get_object_or_404(Result, pk=result_id)
        last_trial = result.trials.order_by("-trial").first()
        if not last_trial:
            return Response({"error": "لم يتم العثور على محاولة"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            Submission.objects.filter(result_trial=last_trial).delete()
            EssaySubmission.objects.filter(result_trial=last_trial).delete()
            last_trial.delete()
            result.trial = max(0, result.trial - 1)
            if result.trial == 0:
                result.delete()
                return Response({"message": "تم حذف المحاولة بنجاح. تم حذف النتيجة لأن عدد المحاولات وصل إلى صفر"})
            result.save(update_fields=["trial"])
        return Response({"message": "تم حذف المحاولة بنجاح", "new_trial_count": result.trial})


class ExamResultDetailView(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Result.objects.all()

    def get(self, request, result_id):
        result = get_object_or_404(Result.objects.select_related("student", "exam").prefetch_related("trials"), pk=result_id)
        return Response(_result_detail_payload(result, result.active_trial))


class ExamResultDetailForTrialView(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Result.objects.all()

    def get(self, request, result_id, result_trial_id):
        result = get_object_or_404(Result.objects.select_related("student", "exam").prefetch_related("trials"), pk=result_id)
        trial = get_object_or_404(ResultTrial, pk=result_trial_id, result=result)
        data = _result_detail_payload(result, trial)
        data["selected_trial_id"] = trial.id
        return Response(data)


class AllTrialsListView(generics.ListAPIView):
    permission_classes = STAFF_PERMISSIONS
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"result__student": ["exact"], "result__exam": ["exact"], "result__exam__course": ["exact"], "result__exam__unit": ["exact"], "submit_type": ["exact"], "trial": ["exact"]}
    search_fields = ["result__student__name", "result__student__user__username", "result__exam__title"]
    ordering_fields = ["student_started_exam_at", "student_submitted_exam_at", "score", "exam_score", "trial"]
    ordering = ["-student_started_exam_at"]

    def get_queryset(self):
        return ResultTrial.objects.select_related("result__student__user", "result__exam").prefetch_related("submissions__question__answers", "essay_submissions__question").all()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        trials = page if page is not None else queryset
        data = [_result_detail_payload(trial.result, trial) for trial in trials]
        return self.get_paginated_response(data) if page is not None else Response(data)


class ResultTrialsView(generics.ListAPIView):
    permission_classes = STAFF_PERMISSIONS
    serializer_class = ResultTrialSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["submit_type"]

    def get_queryset(self):
        result = get_object_or_404(Result, id=self.kwargs["result_id"])
        return result.trials.all().order_by("trial")


class StudentsTookExamAPIView(generics.ListAPIView):
    serializer_class = FlattenedStudentResultSerializer
    permission_classes = STAFF_PERMISSIONS

    def get_queryset(self):
        exam = get_object_or_404(Exam, id=self.kwargs["exam_id"])
        queryset = Student.objects.filter(result__exam=exam).select_related("user").distinct()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(parent_phone__icontains=search) | Q(user__username__icontains=search))
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["exam_id"] = self.kwargs["exam_id"]
        return context


class StudentsDidNotTakeExamAPIView(generics.ListAPIView):
    serializer_class = StudentDidNotTakeExamSerializer
    permission_classes = STAFF_PERMISSIONS

    def get_queryset(self):
        exam = get_object_or_404(Exam, id=self.kwargs["exam_id"])
        related_course_id = exam.get_related_course()
        subscribed = Student.objects.filter(course_subscriptions__course_id=related_course_id, course_subscriptions__active=True).distinct()
        queryset = subscribed.exclude(result__exam=exam)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(parent_phone__icontains=search) | Q(user__username__icontains=search))
        return queryset.annotate(
            course_subscribed_at=Subquery(
                CourseSubscription.objects.filter(student=OuterRef("pk"), course_id=related_course_id, active=True).order_by("-created_at").values("created_at")[:1]
            )
        )


class ExamsTakenByStudentAPIView(generics.ListAPIView):
    serializer_class = FlattenedExamResultSerializer
    permission_classes = STAFF_PERMISSIONS

    def get_queryset(self):
        student = get_object_or_404(Student, id=self.kwargs["student_id"])
        queryset = Exam.objects.filter(results__student=student).select_related("course", "unit").distinct()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["student_id"] = self.kwargs["student_id"]
        return context


class ExamsNotTakenByStudentAPIView(generics.ListAPIView):
    serializer_class = ExamSerializer
    permission_classes = STAFF_PERMISSIONS

    def get_queryset(self):
        student = get_object_or_404(Student, id=self.kwargs["student_id"])
        course_ids = CourseSubscription.objects.filter(student=student, active=True).values_list("course_id", flat=True)
        queryset = Exam.objects.filter(course_id__in=course_ids).exclude(results__student=student).select_related("course", "unit").distinct()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        return queryset


class CopyExamView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, exam_id):
        serializer = CopyExamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        original = get_object_or_404(Exam, pk=exam_id)
        data = serializer.validated_data
        new_exam = Exam.objects.create(
            title=original.title,
            description=original.description,
            related_to=data["related_to"],
            unit=data.get("unit"),
            course=data.get("course"),
            number_of_questions=original.number_of_questions,
            time_limit=original.time_limit,
            score=original.score,
            passing_percent=original.passing_percent,
            start=original.start,
            end=original.end,
            number_of_allowed_trials=original.number_of_allowed_trials,
            type=original.type,
            easy_questions_count=original.easy_questions_count,
            medium_questions_count=original.medium_questions_count,
            hard_questions_count=original.hard_questions_count,
            show_answers_after_finish=original.show_answers_after_finish,
            order=original.order,
            is_active=original.is_active,
            allow_show_results_at=original.allow_show_results_at,
            allow_show_answers_at=original.allow_show_answers_at,
            is_depends=original.is_depends,
            show_questions_in_random=original.show_questions_in_random,
            ponus=original.ponus,
            ponus_option=original.ponus_option,
        )
        for item in original.exam_questions.all():
            ExamQuestion.objects.create(exam=new_exam, question=item.question, is_active=item.is_active, order=item.order)
        if original.type == ExamType.RANDOM:
            try:
                bank = RandomExamBank.objects.get(exam=original)
                new_bank = RandomExamBank.objects.create(exam=new_exam)
                new_bank.questions.set(bank.questions.all())
            except RandomExamBank.DoesNotExist:
                pass
            for model in original.exam_models.all():
                new_model = ExamModel.objects.create(exam=new_exam, title=model.title, is_active=model.is_active)
                for mq in model.model_questions.all():
                    ExamModelQuestion.objects.create(exam_model=new_model, question=mq.question, is_active=mq.is_active)
        return Response({"id": new_exam.id, "message": "تم نسخ الامتحان بنجاح"}, status=status.HTTP_201_CREATED)


class ExamQuestionReorderAPIView(APIView):
    permission_classes = STAFF_PERMISSIONS

    def post(self, request, *args, **kwargs):
        serializer = ExamQuestionReorderSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            for item in serializer.validated_data:
                ExamQuestion.objects.filter(id=item["exam_question"]).update(order=item["new_order"])
        return Response({"detail": "تمت إعادة ترتيب أسئلة الامتحان بنجاح"})


class CreateOrUpdateTempExamAllowedTimes(APIView):
    permission_classes = [IsAdminUser]
    queryset = TempExamAllowedTimes.objects.all()

    def post(self, request):
        serializer = TempExamAllowedTimesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance, created = TempExamAllowedTimes.objects.get_or_create(id=1, defaults=serializer.validated_data)
        if not created:
            for attr, value in serializer.validated_data.items():
                setattr(instance, attr, value)
            instance.save()
        return Response({"message": "تم تحديث أوقات الامتحانات المؤقتة المسموحة بنجاح", "number_of_allowedtempexams_per_day": instance.number_of_allowedtempexams_per_day})


class AddQuestionSimilarsView(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Question.objects.all()

    def post(self, request, question_id):
        main = get_object_or_404(Question, pk=question_id, is_active=True)
        question_ids, error = _coerce_int_list(request.data.get("question_ids", []))
        if error or not question_ids:
            return Response({"error": "يجب أن يكون question_ids قائمة غير فارغة"}, status=status.HTTP_400_BAD_REQUEST)
        question_ids = [qid for qid in question_ids if qid != int(question_id)]
        questions = Question.objects.filter(id__in=question_ids, is_active=True, question_type=QuestionType.MCQ)
        invalid_ids = set(question_ids) - set(questions.values_list("id", flat=True))
        if invalid_ids:
            return Response({"error": f"معرفات أسئلة غير صالحة أو غير نشطة: {sorted(invalid_ids)}"}, status=status.HTTP_400_BAD_REQUEST)
        currently = set(main.similar_questions.values_list("id", flat=True))
        new_questions = [q for q in questions if q.id not in currently]
        if new_questions:
            main.similar_questions.add(*new_questions)
        return Response({"message": "تم معالجة الأسئلة المتشابهة بنجاح", "main_question_id": main.id, "added_count": len(new_questions), "total_similar_questions": main.similar_questions.count()})


class AdminQuestionBankListCreateView(generics.ListCreateAPIView):
    queryset = AdminQuestionBank.objects.select_related("question", "question__course", "question__unit").order_by("-created")
    serializer_class = AdminQuestionBankSerializer
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = {"question__question_type": ["exact"], "question__course": ["exact"], "question__unit": ["exact"]}
    search_fields = ["question__text"]

    def create(self, request, *args, **kwargs):
        if isinstance(request.data, list):
            return self._bulk_create(request.data)
        if isinstance(request.data, dict) and isinstance(request.data.get("questions"), list):
            return self._bulk_create(request.data["questions"])
        return super().create(request, *args, **kwargs)

    def _bulk_create(self, question_ids):
        question_ids, error = _coerce_int_list(question_ids)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        questions = Question.objects.filter(id__in=question_ids, is_active=True)
        invalid_ids = set(question_ids) - set(questions.values_list("id", flat=True))
        if invalid_ids:
            return Response({"error": f"معرفات أسئلة غير صالحة أو غير نشطة: {sorted(invalid_ids)}"}, status=status.HTTP_400_BAD_REQUEST)
        existing_ids = set(AdminQuestionBank.objects.filter(question_id__in=question_ids).values_list("question_id", flat=True))
        new_ids = set(question_ids) - existing_ids
        AdminQuestionBank.objects.bulk_create([AdminQuestionBank(question_id=qid) for qid in new_ids])
        return Response({"success": True, "summary": {"total_requested": len(question_ids), "successfully_added": len(new_ids), "already_existed": len(existing_ids)}, "details": {"added_question_ids": sorted(new_ids), "already_existed_ids": sorted(existing_ids)}}, status=status.HTTP_201_CREATED)


class AdminQuestionBankDestroyView(generics.DestroyAPIView):
    queryset = AdminQuestionBank.objects.all()
    serializer_class = AdminQuestionBankSerializer
    permission_classes = STAFF_PERMISSIONS


class AdminQuestionBankBulkCreateView(APIView):
    permission_classes = STAFF_PERMISSIONS

    def post(self, request, *args, **kwargs):
        view = AdminQuestionBankListCreateView()
        view.request = request
        return view._bulk_create(request.data.get("questions", []))


class ResultTrialListCreateView(generics.ListCreateAPIView):
    queryset = ResultTrial.objects.select_related("result", "result__student", "result__exam")
    serializer_class = ResultTrialSerializer
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"result": ["exact"], "result__student": ["exact"], "result__exam": ["exact"], "trial": ["exact"], "submit_type": ["exact"]}
    search_fields = ["result__student__name", "result__student__user__username", "result__exam__title"]
    ordering_fields = ["trial", "score", "exam_score", "student_started_exam_at", "student_submitted_exam_at"]
    ordering = ["-student_started_exam_at"]


class ResultTrialRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ResultTrial.objects.select_related("result", "result__student", "result__exam")
    serializer_class = ResultTrialSerializer
    permission_classes = STAFF_PERMISSIONS


class ResultTrialDetailView(APIView):
    permission_classes = STAFF_PERMISSIONS

    def get(self, request, trial_id):
        trial = get_object_or_404(ResultTrial.objects.select_related("result", "result__student", "result__student__user", "result__exam"), id=trial_id)
        return Response(_result_detail_payload(trial.result, trial))


class DeleteFirstResultTrialForExamView(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Exam.objects.all()

    def delete(self, request, exam_id):
        exam = get_object_or_404(Exam, id=exam_id)
        results = Result.objects.filter(exam=exam)
        if not results.exists():
            return Response({"message": "لم يتم العثور على نتائج لهذا الامتحان"}, status=status.HTTP_404_NOT_FOUND)
        deleted_count = 0
        for result in results:
            trial = result.trials.order_by("trial").first()
            if trial:
                trial.delete()
                deleted_count += 1
                result.trial = max(0, result.trial - 1)
                if result.trial:
                    result.save(update_fields=["trial"])
                else:
                    result.delete()
        if deleted_count == 0:
            return Response({"message": "لم يتم العثور على محاولات للحذف لأي نتيجة", "exam_id": exam.id, "exam_title": exam.title}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": f"تم حذف المحاولة الأولى لـ {deleted_count} نتيجة بنجاح", "exam_id": exam.id, "exam_title": exam.title, "trials_deleted": deleted_count})
