import json

from django.db import transaction
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DateTimeField,
    Exists,
    FloatField,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import CustomPageNumberPagination
from exam.models import (
    Answer,
    DifficultyLevel,
    Exam,
    ExamConfig,
    Question,
    QuestionCategory,
    QuestionImage,
    QuestionType,
    Result,
    ResultTrial,
    Submission,
    UnsubscribedExamConfig,
    Year,
)
from exam.serializer_fields import stored_file_url
from exam.services import unsubscribed_trial_quota_status
from student.models import Student

from dashboard.serializers.exam.exam import (
    AnswerSerializer,
    ExamQuestionSerializer,
    ExamSerializer,
    ExamConfigSerializer,
    FlattenedExamResultSerializer,
    FlattenedStudentResultSerializer,
    QuestionCategorySerializer,
    QuestionSerializer,
    ResultSerializer,
    ResultTrialSerializer,
    StudentDidNotTakeExamSerializer,
    StudentUnsubscribedExamLimitSerializer,
    TopStudentResultSerializer,
    UnsubscribedExamConfigSerializer,
    YearSerializer,
    answer_payload_matches_existing,
)


STAFF_PERMISSIONS = [IsAuthenticated, IsAdminUser]


class ResultFilter(filters.FilterSet):
    gender = filters.BaseInFilter(field_name="student__user__gender", lookup_expr="in")
    submitted_by_unsubscribed_user = filters.BooleanFilter(
        method="filter_submitted_by_unsubscribed_user"
    )

    def filter_submitted_by_unsubscribed_user(self, queryset, name, value):
        if value:
            return queryset.filter(trials__submitted_by_unsubscribed_user=True).distinct()
        return queryset.exclude(trials__submitted_by_unsubscribed_user=True).distinct()

    class Meta:
        model = Result
        fields = {
            "student": ["exact"],
            "exam": ["exact"],
            "exam__course": ["exact"],
            "exam__unit": ["exact"],
            "exam__category": ["exact"],
            "exam__years": ["exact"],
        }


class ResultTrialFilter(filters.FilterSet):
    gender = filters.BaseInFilter(field_name="result__student__user__gender", lookup_expr="in")

    class Meta:
        model = ResultTrial
        fields = {
            "result": ["exact"],
            "result__student": ["exact"],
            "result__exam": ["exact"],
            "result__exam__course": ["exact"],
            "result__exam__unit": ["exact"],
            "result__exam__category": ["exact"],
            "result__exam__years": ["exact"],
            "submit_type": ["exact"],
            "trial": ["exact"],
            "submitted_by_unsubscribed_user": ["exact"],
        }


class QuestionFilter(filters.FilterSet):
    years = filters.CharFilter(method="filter_years")

    def filter_years(self, queryset, name, value):
        """Accept comma-separated Year primary keys, values, or a mix."""
        tokens = [token.strip() for token in str(value).split(",") if token.strip()]
        if not tokens:
            return queryset

        year_ids = []
        for token in tokens:
            try:
                year_ids.append(int(token))
            except (TypeError, ValueError):
                continue

        lookup = Q(years__value__in=tokens)
        if year_ids:
            lookup |= Q(years__id__in=year_ids)
        return queryset.filter(lookup).distinct()

    class Meta:
        model = Question
        fields = [
            "course",
            "unit",
            "is_active",
            "difficulty",
            "category",
            "question_type",
        ]


def _bool(value):
    if value is None:
        return None
    return str(value).lower() in {"true", "1", "yes"}


def _nullable_form_value(value):
    """Normalize null-like FormData values for optional relation fields."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {
        "",
        "null",
        "none",
        "undefined",
    }:
        return None
    return value


def _normalize_question_classification(data):
    """Normalize optional classification fields on JSON or multipart input."""
    for field in ("course", "unit", "category"):
        if field in data:
            data[field] = _nullable_form_value(data.get(field))
    if "years" in data and _nullable_form_value(data.get("years")) is None:
        if hasattr(data, "setlist"):
            data.setlist("years", [])
        else:
            data["years"] = []
    return data


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


def _exam_course_filter(course_id):
    return Q(course_id=course_id)


def _question_course_filter(course_id):
    return Q(course_id=course_id)


def _answer_payload_from_request(request, prefix, *, partial=False):
    """Build an answer payload without overwriting omitted PATCH fields."""
    payload = {}
    text_key = f"{prefix}[text]"
    correct_key = f"{prefix}[is_correct]"
    image_key = f"{prefix}[image]"

    if not partial or text_key in request.data:
        payload["text"] = request.data.get(text_key)
    if not partial or correct_key in request.data:
        payload["is_correct"] = bool(_bool(request.data.get(correct_key)))
    if image_key in request.FILES:
        payload["image"] = request.FILES[image_key]
    elif image_key in request.data:
        payload["image"] = _nullable_form_value(request.data.get(image_key))
    elif not partial:
        payload["image"] = None
    return payload


def _has_indexed_answer_payload(request, prefix):
    """Return whether any supported field was supplied for one answer index."""
    keys = (
        f"{prefix}[id]",
        f"{prefix}[text]",
        f"{prefix}[is_correct]",
        f"{prefix}[image]",
    )
    return any(key in request.data or key in request.FILES for key in keys)


def _has_indexed_answers(data):
    return any(str(key).startswith("answers[") and str(key).endswith("][text]") for key in data.keys())


def _question_image_files_from_request(request, prefix="images"):
    """Collect uploaded question images.

    Accepts both indexed form-data keys (`images[0]`, `images[1]`, ...) and
    repeated plain `images` fields. Returns a list of UploadedFile objects.
    """
    files = []
    index = 0
    while f"{prefix}[{index}]" in request.FILES:
        files.append(request.FILES[f"{prefix}[{index}]"])
        index += 1
    if not files:
        files = request.FILES.getlist(prefix)
    return files


def _create_question_images(question, files):
    """Persist uploaded image files as QuestionImage rows for the question."""
    if not files:
        return
    start = question.images.aggregate(max=Max("order"))["max"] or 0
    QuestionImage.objects.bulk_create(
        [
            QuestionImage(question=question, image=file, order=start + offset + 1)
            for offset, file in enumerate(files)
        ]
    )



def _remove_question_images(question, raw_ids):
    """Delete QuestionImage rows by ids; accepts a list, JSON array or comma-separated string."""
    try:
        ids = _parse_year_id_list(raw_ids)
    except ValueError as exc:
        raise ValueError(f"Invalid remove_image_ids: {exc}") from exc
    if ids:
        question.images.filter(id__in=ids).delete()


def _strip_parser_artifacts(data):
    """Remove nested-answer keys without deep-copying uploaded file streams."""

    def keep_key(key):
        key = str(key)
        return key != "answers" and not key.startswith("answers[")

    if hasattr(data, "lists"):
        cleaned = QueryDict(
            "",
            mutable=True,
            encoding=getattr(data, "encoding", None),
        )
        for key, values in data.lists():
            if keep_key(key):
                # setlist creates a new list but keeps UploadedFile instances
                # themselves unchanged, including disk-backed temporary files.
                cleaned.setlist(key, list(values))
        return cleaned

    return {key: value for key, value in data.items() if keep_key(key)}


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
        "question_image": (
            question.images.first().image.url if question.images.first() else None
        ),
        "question_images": [
            {"id": qi.id, "image": qi.image.url} for qi in question.images.all()
        ],
        "question_comment": question.comment,
        "question_years": [
            {"id": y.id, "value": y.value} for y in question.years.all()
        ],
        **_question_explanation_fields(question),
        "selected_answer": selected_answer,
        "is_correct": submission.is_correct,
        "is_solved": submission.is_solved,
        "points": 1,
        "answers": answers,
    }


def _result_detail_payload(result, trial):
    if trial:
        mcq_submissions = (
            Submission.objects.filter(result_trial=trial)
            .select_related("question", "selected_answer", "question__category")
            .prefetch_related("question__answers")
        )
    else:
        mcq_submissions = Submission.objects.none()
    student_answers = [_serialize_trial_answer(item) for item in mcq_submissions]

    is_succeeded = False
    if trial and trial.exam_score:
        is_succeeded = trial.score >= (Exam.PASSING_PERCENT / 100) * trial.exam_score

    unsubscribed_quota = unsubscribed_trial_quota_status(result.student)

    return {
        "active_trial": trial.id if trial else None,
        "trial_number": trial.trial if trial else None,
        "student_id": result.student_id,
        "student_name": result.student.name,
        "student_gender": result.student.user.gender,
        "exam_id": result.exam_id,
        "exam_title": result.exam.title,
        "exam_description": None,
        "exam_score": trial.exam_score if trial else 0,
        "student_score": trial.score if trial else 0,
        "is_succeeded": is_succeeded,
        "has_unsubscribed_submission": result.has_unsubscribed_submission,
        "submitted_by_unsubscribed_user": trial.submitted_by_unsubscribed_user if trial else False,
        "unsubscribed_exam_max_trials": unsubscribed_quota['limits']['total'],
        "unsubscribed_exam_trials_used": unsubscribed_quota['usage']['total'],
        "unsubscribed_exam_trials_remaining": unsubscribed_quota['remaining']['total'],
        "student_trials": result.trial,
        "is_trials_finished": result.is_trials_finished,
        "number_of_mcq": mcq_submissions.count(),
        "correct_mcq_count": mcq_submissions.filter(is_correct=True).count(),
        "incorrect_mcq_count": mcq_submissions.filter(is_correct=False, is_solved=True).count(),
        "unsolved_mcq_count": mcq_submissions.filter(is_solved=False).count(),
        "student_answers": student_answers,
        "trials": [
            {
                "trial_number": item.trial,
                "score": item.score,
                "exam_score": item.exam_score,
                "student_started_exam_at": item.student_started_exam_at,
                "student_submitted_exam_at": item.student_submitted_exam_at,
                "submit_type": item.submit_type,
                "submitted_by_unsubscribed_user": item.submitted_by_unsubscribed_user,
                "trial_id": item.id,
                "is_active": trial and item.id == trial.id,
            }
            for item in result.trials.all().order_by("trial")
        ],
        "student_started_exam_at": trial.student_started_exam_at if trial else None,
        "student_submitted_exam_at": trial.student_submitted_exam_at if trial else None,
        "submit_type": trial.submit_type if trial else None,
    }


class ExamListCreateView(generics.ListAPIView):
    serializer_class = ExamSerializer
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ["student", "course", "unit", "category", "years", "created"]
    search_fields = [
        "title", "course__name", "unit__name", "category__title",
        "years__value", "student__name", "student__user__username", "student__code",
    ]
    ordering_fields = ["created", "title", "number_of_questions", "time_limit"]
    ordering = ["-created", "-id"]

    def get_queryset(self):
        return Exam.objects.select_related(
            "student", "student__user", "course", "unit", "category"
        ).prefetch_related("years").annotate(
            result_count=Count('results', distinct=True),
            trial_count=Count('results__trials', distinct=True),
        ).distinct()


class ExamDetailView(generics.RetrieveAPIView):
    queryset = Exam.objects.select_related(
        "student", "student__user", "course", "unit", "category"
    ).prefetch_related("years").annotate(
        result_count=Count('results', distinct=True),
        trial_count=Count('results__trials', distinct=True),
    )
    serializer_class = ExamSerializer
    permission_classes = STAFF_PERMISSIONS


class ExamConfigView(APIView):
    permission_classes = STAFF_PERMISSIONS

    def get(self, request):
        return Response(ExamConfigSerializer(ExamConfig.load()).data)

    def patch(self, request):
        serializer = ExamConfigSerializer(
            ExamConfig.load(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UnsubscribedExamConfigView(APIView):
    permission_classes = STAFF_PERMISSIONS

    def get(self, request):
        return Response(
            UnsubscribedExamConfigSerializer(UnsubscribedExamConfig.load()).data
        )

    def patch(self, request):
        serializer = UnsubscribedExamConfigSerializer(
            UnsubscribedExamConfig.load(),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class StudentUnsubscribedExamLimitView(generics.RetrieveUpdateAPIView):
    queryset = Student.objects.select_related('user')
    serializer_class = StudentUnsubscribedExamLimitSerializer
    permission_classes = STAFF_PERMISSIONS
    lookup_url_kwarg = 'student_id'


class StudentUnsubscribedExamLimitListView(generics.ListAPIView):
    """Search students and inspect their effective guest main-exam allowance."""

    serializer_class = StudentUnsubscribedExamLimitSerializer
    permission_classes = STAFF_PERMISSIONS
    pagination_class = CustomPageNumberPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'user__username', 'code', 'parent_phone']
    ordering_fields = [
        'id',
        'name',
        'created_at',
        'unsubscribed_exam_max_trials',
        'unsubscribed_trials_used',
    ]
    ordering = ['name', 'id']

    def get_queryset(self):
        unsubscribed_usage = (
            ResultTrial.objects.filter(
                result__student_id=OuterRef('pk'),
                result__exam__student_id=OuterRef('pk'),
                submitted_by_unsubscribed_user=True,
            )
            .values('result__student_id')
            .annotate(total=Count('id'))
            .values('total')[:1]
        )
        queryset = Student.objects.select_related('user').annotate(
            unsubscribed_trials_used=Coalesce(
                Subquery(unsubscribed_usage, output_field=IntegerField()),
                Value(0),
            )
        )
        has_custom_limit = self.request.query_params.get('has_custom_limit')
        if has_custom_limit is not None:
            if _bool(has_custom_limit):
                queryset = queryset.filter(unsubscribed_exam_max_trials__isnull=False)
            else:
                queryset = queryset.filter(unsubscribed_exam_max_trials__isnull=True)
        return queryset


class QuestionCategoryListCreateView(generics.ListCreateAPIView):
    queryset = QuestionCategory.objects.select_related("course").order_by("id")
    permission_classes = STAFF_PERMISSIONS
    serializer_class = QuestionCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["course"]


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


class YearListAllView(generics.ListAPIView):
    queryset = Year.objects.all().order_by("-value")
    serializer_class = YearSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class YearRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Year.objects.all()
    serializer_class = YearSerializer
    permission_classes = STAFF_PERMISSIONS


class QuestionListCreateView(generics.ListCreateAPIView):
    queryset = (
        Question.objects
        .select_related("course", "unit", "category")
        .prefetch_related("answers", "years", "images")
        .order_by("-created", "-id")
    )
    permission_classes = STAFF_PERMISSIONS
    serializer_class = QuestionSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = (DjangoFilterBackend, SearchFilter)
    filterset_class = QuestionFilter
    search_fields = ["text", "answers__text"]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if "answers" in request.data and not _has_indexed_answers(request.data):
            return super().create(request, *args, **kwargs)
        data = _normalize_question_classification(
            _strip_parser_artifacts(request.data)
        )
        if "explanation_video_url" in request.FILES:
            data["explanation_video_url"] = request.FILES["explanation_video_url"]
        if "explanation_recorded_audio" in request.FILES:
            data["explanation_recorded_audio"] = request.FILES["explanation_recorded_audio"]
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save()

        # Multiple images (images[0], images[1], ... or repeated `images` files)
        _create_question_images(question, _question_image_files_from_request(request))

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
    queryset = Question.objects.select_related("course", "unit", "category").prefetch_related("answers", "images")
    serializer_class = QuestionSerializer
    permission_classes = STAFF_PERMISSIONS
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()

        if "answers" in request.data and not _has_indexed_answers(request.data):
            return super().patch(request, *args, **kwargs)

        data = _normalize_question_classification(
            _strip_parser_artifacts(request.data)
        )
        if "explanation_video_url" in request.FILES:
            data["explanation_video_url"] = request.FILES["explanation_video_url"]
        if "explanation_recorded_audio" in request.FILES:
            data["explanation_recorded_audio"] = request.FILES["explanation_recorded_audio"]

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Multiple images: append new uploads and/or remove existing rows by id.
        _create_question_images(instance, _question_image_files_from_request(request))
        if request.data.get("remove_image_ids") not in (None, ""):
            try:
                _remove_question_images(instance, request.data.get("remove_image_ids"))
            except ValueError as exc:
                raise ValidationError({"remove_image_ids": [str(exc)]}) from exc

        answer_entries = []
        index = 0
        while _has_indexed_answer_payload(request, f"answers[{index}]"):
            prefix = f"answers[{index}]"
            answer_id = request.data.get(f"{prefix}[id]")
            payload = _answer_payload_from_request(
                request,
                prefix,
                partial=True,
            )
            answer_entries.append((answer_id, payload))
            index += 1

        # Process updates before creations. Some clients can accidentally send
        # the edited answer twice: once with its id and once without it. After
        # the id-based update, the duplicate payload matches and is ignored.
        for answer_id, payload in answer_entries:
            if answer_id:
                answer = get_object_or_404(Answer, id=answer_id, question=instance)
                answer_serializer = AnswerSerializer(answer, data=payload, partial=True)
                answer_serializer.is_valid(raise_exception=True)
                answer_serializer.save()

        for answer_id, payload in answer_entries:
            if answer_id or answer_payload_matches_existing(instance, payload):
                continue
            payload["question"] = instance.id
            answer_serializer = AnswerSerializer(data=payload)
            answer_serializer.is_valid(raise_exception=True)
            answer_serializer.save()

        instance = self.get_object()
        return Response(self.get_serializer(instance).data)


class BulkQuestionCreateView(generics.CreateAPIView):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = STAFF_PERMISSIONS

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if "questions[0][text]" not in request.data:
            raise ValidationError(
                {"questions": ["At least one question is required."]}
            )
        created_questions = []

        index = 0
        while f"questions[{index}][text]" in request.data:
            data = {
                "text": request.data.get(f"questions[{index}][text]"),
                "points": request.data.get(f"questions[{index}][points]"),
                "difficulty": request.data.get(f"questions[{index}][difficulty]"),
                "category": _nullable_form_value(
                    request.data.get(f"questions[{index}][category]")
                ),
                "course": _nullable_form_value(
                    request.data.get(f"questions[{index}][course]")
                ),
                "unit": _nullable_form_value(
                    request.data.get(f"questions[{index}][unit]")
                ),
                "question_type": request.data.get(f"questions[{index}][question_type]"),
                "comment": request.data.get(f"questions[{index}][comment]"),
                "explanation_text": request.data.get(
                    f"questions[{index}][explanation_text]",
                    request.data.get(f"questions[{index}][explanation]"),
                ),
            }
            video_key = f"questions[{index}][explanation_video_url]"
            if video_key in request.FILES:
                data["explanation_video_url"] = request.FILES[video_key]
            elif request.data.get(video_key) not in (None, ""):
                # Let the FileField return a clear validation error for
                # obsolete URL/text input instead of silently ignoring it.
                data["explanation_video_url"] = request.data.get(video_key)
            audio_key = f"questions[{index}][explanation_recorded_audio]"
            if audio_key in request.FILES:
                data["explanation_recorded_audio"] = request.FILES[audio_key]
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            question = serializer.save()

            # Multiple images: questions[i][images][j] files (or repeated questions[i][images])
            _create_question_images(
                question,
                _question_image_files_from_request(request, f"questions[{index}][images]"),
            )

            # Attach years (list of Year primary keys).
            # Accepts JSON-array string "[1,4,2]", comma-separated "1,4,2",
            # or repeated fields. Years are looked up by ID; an unknown ID
            # returns 400.
            years_raw = _nullable_form_value(
                request.data.get(f"questions[{index}][years]")
            )
            if years_raw not in (None, ""):
                try:
                    year_ids = _parse_year_id_list(years_raw)
                except ValueError as exc:
                    raise ValidationError(
                        {f"questions[{index}][years]": [str(exc)]}
                    ) from exc
                if year_ids:
                    existing = Year.objects.filter(id__in=year_ids)
                    missing = sorted(
                        set(year_ids) - set(existing.values_list("id", flat=True))
                    )
                    if missing:
                        raise ValidationError(
                            {
                                f"questions[{index}][years]": ["سنة غير موجودة"],
                                "missing_year_ids": missing,
                            }
                        )
                    question.years.set(existing)

            answer_index = 0
            while f"questions[{index}][answers][{answer_index}][text]" in request.data:
                payload = _answer_payload_from_request(
                    request,
                    f"questions[{index}][answers][{answer_index}]",
                )
                payload["question"] = question.id
                answer_serializer = AnswerSerializer(data=payload)
                answer_serializer.is_valid(raise_exception=True)
                answer_serializer.save()
                answer_index += 1
            created_questions.append(question)
            index += 1

        data = self.get_serializer(created_questions, many=True).data
        return Response(data, status=status.HTTP_201_CREATED)


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


class ExamQuestionListCreateView(generics.ListAPIView):
    http_method_names = ['get', 'head', 'options']
    permission_classes = STAFF_PERMISSIONS
    serializer_class = ExamQuestionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "question__category": ["exact"],
        "question__course": ["exact"],
        "question__unit": ["exact"],
        "question__question_type": ["exact"],
        "question__difficulty": ["exact"],
        "question__is_active": ["exact"],
        "is_active": ["exact"],
    }
    search_fields = ["question__text"]
    ordering_fields = ["order", "id", "created", "question__points"]
    ordering = ["order", "id"]

    def get_queryset(self):
        exam = get_object_or_404(Exam, pk=self.kwargs["exam_id"])
        return exam.exam_questions.select_related("question").all()

class ResultListView(generics.ListAPIView):
    serializer_class = ResultSerializer
    pagination_class = CustomPageNumberPagination
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ResultFilter
    search_fields = ["student__name", "student__user__username", "exam__title"]
    ordering_fields = ["added", "trial"]
    ordering = ["-added"]

    def get_queryset(self):
        unsubscribed_usage = (
            ResultTrial.objects.filter(
                result__student_id=OuterRef('student_id'),
                result__exam__student_id=OuterRef('student_id'),
                submitted_by_unsubscribed_user=True,
            )
            .values('result__student_id')
            .annotate(total=Count('id'))
            .values('total')[:1]
        )
        queryset = Result.objects.filter(trials__isnull=False).select_related(
            "student", "student__user", "exam", "exam__course", "exam__unit"
        ).prefetch_related("trials").annotate(
            unsubscribed_trials_used=Coalesce(
                Subquery(unsubscribed_usage, output_field=IntegerField()),
                Value(0),
            )
        ).distinct()
        submitted = self.request.query_params.get("submitted")
        if submitted is not None:
            if _bool(submitted):
                queryset = queryset.filter(trials__student_submitted_exam_at__isnull=False).distinct()
            else:
                queryset = queryset.filter(trials__student_submitted_exam_at__isnull=True).distinct()
        return queryset


class TopStudentResultsView(generics.ListAPIView):
    """Return the ten students with the highest sum of dashboard result scores."""

    serializer_class = TopStudentResultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = [
        "name",
        "user__username",
        "code",
        "parent_phone",
    ]

    def get_queryset(self):
        # Result.active_trial uses the latest submitted trial, falling back to
        # the current trial only when the result has never been submitted.
        active_trial = (
            ResultTrial.objects.filter(result_id=OuterRef("pk"))
            .annotate(
                is_submitted=Case(
                    When(student_submitted_exam_at__isnull=False, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )
            .order_by("-is_submitted", "-trial")
        )

        result_totals = (
            Result.objects.filter(student_id=OuterRef("pk"))
            .annotate(
                has_trial=Exists(
                    ResultTrial.objects.filter(result_id=OuterRef("pk"))
                )
            )
            .filter(has_trial=True)
            .annotate(
                active_score=Coalesce(
                    Subquery(
                        active_trial.values("score")[:1],
                        output_field=FloatField(),
                    ),
                    Value(0.0),
                ),
                active_exam_score=Coalesce(
                    Subquery(
                        active_trial.values("exam_score")[:1],
                        output_field=FloatField(),
                    ),
                    Value(0.0),
                ),
            )
            .values("student_id")
            .annotate(
                total_student_score=Sum("active_score"),
                total_exam_score=Sum("active_exam_score"),
                result_count=Count("id"),
            )
        )

        return (
            Student.objects.filter(
                id__in=Result.objects.filter(
                    trials__isnull=False
                ).values("student_id")
            )
            .select_related("user")
            .annotate(
                total_student_score=Coalesce(
                    Subquery(
                        result_totals.values("total_student_score")[:1],
                        output_field=FloatField(),
                    ),
                    Value(0.0),
                ),
                total_exam_score=Coalesce(
                    Subquery(
                        result_totals.values("total_exam_score")[:1],
                        output_field=FloatField(),
                    ),
                    Value(0.0),
                ),
                results_count=Coalesce(
                    Subquery(
                        result_totals.values("result_count")[:1],
                        output_field=IntegerField(),
                    ),
                    Value(0),
                ),
            )
            .order_by("-total_student_score", "id")
        )

    def list(self, request, *args, **kwargs):
        students = list(self.filter_queryset(self.get_queryset())[:10])
        for rank, student in enumerate(students, start=1):
            student.rank = rank

        data = self.get_serializer(students, many=True).data
        return Response(
            {
                "count": len(data),
                "next": None,
                "previous": None,
                "results": data,
            }
        )


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
        result = get_object_or_404(Result.objects.select_related("student__user", "exam").prefetch_related("trials"), pk=result_id)
        return Response(_result_detail_payload(result, result.active_trial))


class ExamResultDetailForTrialView(APIView):
    permission_classes = STAFF_PERMISSIONS
    queryset = Result.objects.all()

    def get(self, request, result_id, result_trial_id):
        result = get_object_or_404(Result.objects.select_related("student__user", "exam").prefetch_related("trials"), pk=result_id)
        trial = get_object_or_404(ResultTrial, pk=result_trial_id, result=result)
        data = _result_detail_payload(result, trial)
        data["selected_trial_id"] = trial.id
        return Response(data)


class AllTrialsListView(generics.ListAPIView):
    permission_classes = STAFF_PERMISSIONS
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ResultTrialFilter
    search_fields = ["result__student__name", "result__student__user__username", "result__exam__title"]
    ordering_fields = ["student_started_exam_at", "student_submitted_exam_at", "score", "exam_score", "trial"]
    ordering = ["-student_started_exam_at"]

    def get_queryset(self):
        return ResultTrial.objects.select_related(
            "result__student__user", "result__exam"
        ).prefetch_related("submissions__question__answers")

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
    filterset_fields = ["submit_type", "submitted_by_unsubscribed_user"]

    def get_queryset(self):
        result = get_object_or_404(Result, id=self.kwargs["result_id"])
        return result.trials.all().order_by("trial")


class StudentsTookExamAPIView(generics.ListAPIView):
    serializer_class = FlattenedStudentResultSerializer
    permission_classes = STAFF_PERMISSIONS

    def get_queryset(self):
        exam = get_object_or_404(Exam, id=self.kwargs["exam_id"])
        queryset = Student.objects.filter(
            result__exam=exam,
            result__trials__isnull=False,
        ).select_related("user").distinct()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(parent_phone__icontains=search) | Q(user__username__icontains=search))
        gender = self.request.query_params.get("gender")
        if gender:
            queryset = queryset.filter(user__gender__in=[value.strip() for value in gender.split(",") if value.strip()])
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
        taken_trial = ResultTrial.objects.filter(
            result__exam=exam,
            result__student_id=OuterRef("pk"),
        )
        queryset = Student.objects.filter(pk=exam.student_id).annotate(
            has_taken_exam=Exists(taken_trial)
        ).filter(has_taken_exam=False)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(parent_phone__icontains=search) | Q(user__username__icontains=search))
        gender = self.request.query_params.get("gender")
        if gender:
            queryset = queryset.filter(user__gender__in=[value.strip() for value in gender.split(",") if value.strip()])
        return queryset.annotate(course_subscribed_at=Value(None, output_field=DateTimeField()))


class ExamsTakenByStudentAPIView(generics.ListAPIView):
    serializer_class = FlattenedExamResultSerializer
    permission_classes = STAFF_PERMISSIONS

    def get_queryset(self):
        student = get_object_or_404(Student, id=self.kwargs["student_id"])
        queryset = Exam.objects.filter(
            results__student=student,
            results__trials__isnull=False,
        ).select_related("course", "unit").distinct()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(title__icontains=search))
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
        taken_trial = ResultTrial.objects.filter(
            result__student=student,
            result__exam_id=OuterRef("pk"),
        )
        queryset = Exam.objects.filter(student=student).annotate(
            has_been_taken=Exists(taken_trial)
        ).filter(has_been_taken=False).select_related(
            "student", "course", "unit", "category"
        ).distinct()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(title__icontains=search))
        return queryset


class ResultTrialListCreateView(generics.ListAPIView):
    queryset = ResultTrial.objects.select_related("result", "result__student__user", "result__exam")
    serializer_class = ResultTrialSerializer
    permission_classes = STAFF_PERMISSIONS
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ResultTrialFilter
    search_fields = ["result__student__name", "result__student__user__username", "result__exam__title"]
    ordering_fields = ["trial", "score", "exam_score", "student_started_exam_at", "student_submitted_exam_at"]
    ordering = ["-student_started_exam_at"]


class ResultTrialRetrieveUpdateDestroyView(generics.RetrieveAPIView):
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

    @transaction.atomic
    def delete(self, request, exam_id):
        exam = get_object_or_404(Exam, id=exam_id)
        results = Result.objects.select_for_update().filter(exam=exam)
        if not results.exists():
            return Response({"message": "لم يتم العثور على نتائج لهذا الامتحان"}, status=status.HTTP_404_NOT_FOUND)
        deleted_count = 0
        for result in results:
            trial = result.trials.select_for_update().order_by("trial", "id").first()
            if trial:
                Submission.objects.filter(result_trial=trial).delete()
                trial.delete()
                deleted_count += 1
                remaining_trials = list(result.trials.order_by("trial", "id"))
                if not remaining_trials:
                    result.delete()
                    continue
                for new_number, remaining_trial in enumerate(remaining_trials, start=1):
                    if remaining_trial.trial != new_number:
                        remaining_trial.trial = new_number
                        remaining_trial.save(update_fields=["trial"])
                result.trial = len(remaining_trials)
                result.save(update_fields=["trial"])
        if deleted_count == 0:
            return Response({"message": "لم يتم العثور على محاولات للحذف لأي نتيجة", "exam_id": exam.id, "exam_title": exam.title}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": f"تم حذف المحاولة الأولى لـ {deleted_count} نتيجة بنجاح", "exam_id": exam.id, "exam_title": exam.title, "trials_deleted": deleted_count})
