from rest_framework import serializers

from exam.models import (
    Answer,
    Exam,
    ExamConfig,
    ExamQuestion,
    Question,
    QuestionCategory,
    QuestionImage,
    Result,
    ResultTrial,
    UnsubscribedExamConfig,
    Year,
)
from student.models import Student
from exam.serializer_fields import StoredFileField
from exam.services import unsubscribed_trial_quota_status


class QuestionImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionImage
        fields = ["id", "image", "order"]


class AnswerSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Answer
        fields = ["id", "text", "image", "is_correct", "question"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "question": {"required": False},
            "is_correct": {"required": False, "default": False},
        }


def answer_payload_matches_existing(question, payload):
    """Return whether the supplied answer fields already match an answer.

    This is used by partial question updates to ignore a duplicated no-id
    answer row after its corresponding id-based row has been updated.  Only
    scalar fields are compared; an uploaded image without an answer id is a
    genuine new-answer payload and must still go through normal validation.
    """
    lookup = {
        field: payload[field]
        for field in ("text", "is_correct")
        if field in payload
    }
    return bool(lookup) and question.answers.filter(**lookup).exists()


class QuestionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, required=False)
    images = QuestionImageSerializer(many=True, read_only=True)
    explanation_video_url = StoredFileField(required=False, allow_null=True)
    course_name = serializers.CharField(
        source="course.name", read_only=True, default=None
    )
    unit_name = serializers.CharField(
        source="unit.name", read_only=True, default=None
    )
    category_name = serializers.CharField(
        source="category.title", read_only=True, default=None
    )
    years = serializers.ManyRelatedField(
        child_relation=serializers.PrimaryKeyRelatedField(
            queryset=Year.objects.all(),
        ),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "explanation_text",
            "explanation_video_url",
            "explanation_recorded_audio",
            "images",
            "points",
            "difficulty",
            "category",
            "category_name",
            "course",
            "course_name",
            "unit",
            "unit_name",
            "is_active",
            "answers",
            "question_type",
            "comment",
            "created",
            "years",
        ]
        read_only_fields = ["id", "created"]

    def validate(self, attrs):
        if self.instance is None and "is_active" not in getattr(self, "initial_data", {}):
            attrs["is_active"] = True
        unit = attrs.get("unit", getattr(self.instance, "unit", None))
        if unit:
            attrs["course"] = unit.course
        return attrs

    def create(self, validated_data):
        answers_data = validated_data.pop("answers", [])
        years_data = validated_data.pop("years", [])
        question = Question.objects.create(**validated_data)
        if years_data:
            question.years.set(years_data)
        for answer_data in answers_data:
            Answer.objects.create(question=question, **answer_data)
        return question

    def update(self, instance, validated_data):
        answers_data = validated_data.pop("answers", None)
        years_data = validated_data.pop("years", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if years_data is not None:
            instance.years.set(years_data)

        if answers_data is not None:
            raw_answers = self.initial_data.get("answers", [])
            processed_ids = []
            entries = [
                (
                    raw_answers[i].get("id") if i < len(raw_answers) else None,
                    answer_data,
                )
                for i, answer_data in enumerate(answers_data)
            ]

            # Update id-based rows first so a repeated no-id row can be
            # recognized against the answer's new state instead of inserted.
            for raw_id, answer_data in entries:
                if raw_id and instance.answers.filter(id=raw_id).exists():
                    Answer.objects.filter(id=raw_id, question=instance).update(**answer_data)
                    processed_ids.append(int(raw_id))

            for raw_id, answer_data in entries:
                if raw_id:
                    continue
                if self.partial and answer_payload_matches_existing(instance, answer_data):
                    continue
                else:
                    answer = Answer.objects.create(question=instance, **answer_data)
                    processed_ids.append(answer.id)

            if not self.partial:
                instance.answers.exclude(id__in=processed_ids).delete()
            try:
                del instance._prefetched_objects_cache['answers']
            except (AttributeError, KeyError):
                pass
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["answers"] = AnswerSerializer(instance.answers.all(), many=True, context=self.context).data
        data["years"] = YearSerializer(instance.years.all(), many=True, context=self.context).data
        return data


class ExamSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_phone = serializers.CharField(source='student.user.username', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    category_name = serializers.CharField(source='category.title', read_only=True)
    score = serializers.IntegerField(read_only=True)
    passing_percent = serializers.IntegerField(read_only=True)
    result_count = serializers.IntegerField(read_only=True)
    trial_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "student",
            "student_name",
            "student_phone",
            "title",
            "course",
            "course_name",
            "unit",
            "unit_name",
            "category",
            "category_name",
            "years",
            "number_of_questions",
            "easy_questions_count",
            "medium_questions_count",
            "hard_questions_count",
            "time_limit",
            "score",
            "passing_percent",
            "created",
            "status",
            "result_count",
            "trial_count",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return obj.status()


class ExamConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamConfig
        fields = [
            'max_trials_per_day',
            'max_trials_per_week',
            'max_trials_per_month',
        ]

    def validate(self, attrs):
        instance = self.instance or ExamConfig()
        daily = attrs.get('max_trials_per_day', instance.max_trials_per_day)
        weekly = attrs.get('max_trials_per_week', instance.max_trials_per_week)
        monthly = attrs.get('max_trials_per_month', instance.max_trials_per_month)
        if daily > weekly:
            raise serializers.ValidationError('max_trials_per_week must be at least max_trials_per_day.')
        if weekly > monthly:
            raise serializers.ValidationError('max_trials_per_month must be at least max_trials_per_week.')
        return attrs


class UnsubscribedExamConfigSerializer(serializers.ModelSerializer):
    max_trials = serializers.IntegerField(min_value=0)
    max_questions_per_exam = serializers.IntegerField(min_value=1)

    class Meta:
        model = UnsubscribedExamConfig
        fields = ['max_trials', 'max_questions_per_exam']


class StudentUnsubscribedExamLimitSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source='id', read_only=True)
    student_name = serializers.CharField(source='name', read_only=True)
    student_phone = serializers.CharField(source='user.username', read_only=True)
    max_trials = serializers.IntegerField(
        source='unsubscribed_exam_max_trials',
        min_value=0,
        allow_null=True,
        required=False,
    )
    effective_max_trials = serializers.SerializerMethodField()
    used_trials = serializers.SerializerMethodField()
    remaining_trials = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'student_id',
            'student_name',
            'student_phone',
            'max_trials',
            'effective_max_trials',
            'used_trials',
            'remaining_trials',
            'can_start',
        ]

    def _quota(self, obj):
        if not hasattr(self, '_quota_cache'):
            self._quota_cache = {}
        if obj.id not in self._quota_cache:
            annotated_usage = getattr(obj, 'unsubscribed_trials_used', None)
            if annotated_usage is None:
                quota = unsubscribed_trial_quota_status(obj)
            else:
                if not hasattr(self, '_unsubscribed_exam_config'):
                    self._unsubscribed_exam_config = UnsubscribedExamConfig.load()
                limit = (
                    self._unsubscribed_exam_config.max_trials
                    if obj.unsubscribed_exam_max_trials is None
                    else obj.unsubscribed_exam_max_trials
                )
                quota = {
                    'limits': {'total': limit},
                    'usage': {'total': annotated_usage},
                    'remaining': {'total': max(limit - annotated_usage, 0)},
                    'can_start': annotated_usage < limit,
                }
            self._quota_cache[obj.id] = quota
        return self._quota_cache[obj.id]

    def get_effective_max_trials(self, obj):
        return self._quota(obj)['limits']['total']

    def get_used_trials(self, obj):
        return self._quota(obj)['usage']['total']

    def get_remaining_trials(self, obj):
        return self._quota(obj)['remaining']['total']

    def get_can_start(self, obj):
        return self._quota(obj)['can_start']


class QuestionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionCategory
        fields = ["id", "title", "course"]


class YearSerializer(serializers.ModelSerializer):
    class Meta:
        model = Year
        fields = ["id", "value"]


class ResultTrialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultTrial
        fields = [
            "id",
            "result",
            "trial",
            "score",
            "exam_score",
            "submit_type",
            "student_started_exam_at",
            "student_submitted_exam_at",
            "submitted_by_unsubscribed_user",
        ]
        read_only_fields = ["id", "submitted_by_unsubscribed_user"]


class ResultSerializer(serializers.ModelSerializer):
    result_id = serializers.IntegerField(source="id")
    exam_id = serializers.IntegerField()
    exam_score = serializers.SerializerMethodField()
    student_score = serializers.SerializerMethodField()
    correct_questions_count = serializers.SerializerMethodField()
    incorrect_questions_count = serializers.SerializerMethodField()
    insolved_questions_count = serializers.SerializerMethodField()
    allowed_to_show_result = serializers.SerializerMethodField()
    trials = serializers.IntegerField(source="trial")
    number_of_allowed_trials = serializers.SerializerMethodField()
    student_id = serializers.IntegerField()
    student_name = serializers.SerializerMethodField()
    student_phone = serializers.SerializerMethodField()
    student_gender = serializers.SerializerMethodField()
    parent_phone = serializers.SerializerMethodField()
    student_started_exam_at = serializers.SerializerMethodField()
    student_submitted_exam_at = serializers.SerializerMethodField()
    submit_type = serializers.SerializerMethodField()
    has_unsubscribed_submission = serializers.BooleanField(read_only=True)
    submitted_by_unsubscribed_user = serializers.SerializerMethodField()
    unsubscribed_exam_max_trials = serializers.SerializerMethodField()
    unsubscribed_exam_trials_used = serializers.SerializerMethodField()
    unsubscribed_exam_trials_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = [
            "result_id",
            "exam_id",
            "exam_score",
            "student_score",
            "trials",
            "number_of_allowed_trials",
            "correct_questions_count",
            "incorrect_questions_count",
            "insolved_questions_count",
            "allowed_to_show_result",
            "student_id",
            "student_name",
            "student_phone",
            "student_gender",
            "parent_phone",
            "student_started_exam_at",
            "student_submitted_exam_at",
            "submit_type",
            "has_unsubscribed_submission",
            "submitted_by_unsubscribed_user",
            "unsubscribed_exam_max_trials",
            "unsubscribed_exam_trials_used",
            "unsubscribed_exam_trials_remaining",
        ]

    def _active_trial(self, obj):
        return getattr(obj, "active_trial", None)

    def get_exam_score(self, obj):
        trial = self._active_trial(obj)
        return getattr(obj, "exam_score", None) if hasattr(obj, "exam_score") else (trial.exam_score if trial else 0)

    def get_student_score(self, obj):
        trial = self._active_trial(obj)
        return getattr(obj, "student_score", None) if hasattr(obj, "student_score") else (trial.score if trial else 0)

    def get_correct_questions_count(self, obj):
        return getattr(obj, "correct_questions_count", 0)

    def get_incorrect_questions_count(self, obj):
        return getattr(obj, "incorrect_questions_count", 0)

    def get_insolved_questions_count(self, obj):
        return getattr(obj, "unsolved_questions_count", 0)

    def get_allowed_to_show_result(self, obj):
        return obj.is_allowed_to_show_result if hasattr(obj, "is_allowed_to_show_result") else False

    def get_number_of_allowed_trials(self, obj):
        trial = self._active_trial(obj)
        if trial and trial.submitted_by_unsubscribed_user:
            return self._unsubscribed_quota(obj)['limits']['total']
        if not hasattr(self, '_main_exam_daily_limit'):
            self._main_exam_daily_limit = ExamConfig.load().max_trials_per_day
        return self._main_exam_daily_limit

    def _unsubscribed_quota(self, obj):
        if not hasattr(self, '_unsubscribed_quota_cache'):
            self._unsubscribed_quota_cache = {}
        if obj.student_id not in self._unsubscribed_quota_cache:
            annotated_usage = getattr(obj, 'unsubscribed_trials_used', None)
            if annotated_usage is None:
                quota = unsubscribed_trial_quota_status(obj.student)
            else:
                if not hasattr(self, '_unsubscribed_exam_config'):
                    self._unsubscribed_exam_config = UnsubscribedExamConfig.load()
                custom_limit = obj.student.unsubscribed_exam_max_trials
                limit = (
                    self._unsubscribed_exam_config.max_trials
                    if custom_limit is None
                    else custom_limit
                )
                quota = {
                    'limits': {'total': limit},
                    'usage': {'total': annotated_usage},
                    'remaining': {'total': max(limit - annotated_usage, 0)},
                }
            self._unsubscribed_quota_cache[obj.student_id] = quota
        return self._unsubscribed_quota_cache[obj.student_id]

    def get_unsubscribed_exam_max_trials(self, obj):
        return self._unsubscribed_quota(obj)['limits']['total']

    def get_unsubscribed_exam_trials_used(self, obj):
        return self._unsubscribed_quota(obj)['usage']['total']

    def get_unsubscribed_exam_trials_remaining(self, obj):
        return self._unsubscribed_quota(obj)['remaining']['total']

    def get_student_name(self, obj):
        return getattr(obj.student, "name", getattr(obj, "student_name", ""))

    def get_student_phone(self, obj):
        return getattr(getattr(obj.student, "user", None), "username", getattr(obj, "student_phone", ""))

    def get_student_gender(self, obj):
        return getattr(getattr(obj.student, "user", None), "gender", "not_defined")

    def get_parent_phone(self, obj):
        return getattr(obj.student, "parent_phone", getattr(obj, "parent_phone", ""))

    def get_student_started_exam_at(self, obj):
        trial = self._active_trial(obj)
        return getattr(obj, "student_started_exam_at", None) if hasattr(obj, "student_started_exam_at") else (trial.student_started_exam_at if trial else None)

    def get_student_submitted_exam_at(self, obj):
        trial = self._active_trial(obj)
        return getattr(obj, "student_submitted_exam_at", None) if hasattr(obj, "student_submitted_exam_at") else (trial.student_submitted_exam_at if trial else None)

    def get_submit_type(self, obj):
        trial = self._active_trial(obj)
        return getattr(obj, "submit_type", None) if hasattr(obj, "submit_type") else (trial.submit_type if trial else None)

    def get_submitted_by_unsubscribed_user(self, obj):
        trial = self._active_trial(obj)
        return trial.submitted_by_unsubscribed_user if trial else False


class TopStudentResultSerializer(serializers.ModelSerializer):
    """Aggregate leaderboard row shaped like the student part of a result row."""

    rank = serializers.IntegerField(read_only=True)
    student_id = serializers.IntegerField(source="id", read_only=True)
    student_name = serializers.CharField(source="name", read_only=True)
    student_phone = serializers.CharField(source="user.username", read_only=True)
    student_gender = serializers.CharField(source="user.gender", read_only=True)
    student_score = serializers.FloatField(source="total_student_score", read_only=True)
    exam_score = serializers.FloatField(source="total_exam_score", read_only=True)
    results_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Student
        fields = [
            "rank",
            "student_id",
            "student_name",
            "student_phone",
            "student_gender",
            "parent_phone",
            "student_score",
            "exam_score",
            "results_count",
        ]


class BriefedResultSerializer(serializers.ModelSerializer):
    examscore = serializers.SerializerMethodField()
    student_score = serializers.SerializerMethodField()
    issucceeded = serializers.BooleanField(source="is_succeeded")
    exam_title = serializers.CharField(source="exam.title", read_only=True)
    trials = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = ["id", "exam", "exam_title", "examscore", "student_score", "trial", "is_trials_finished", "issucceeded", "added", "trials"]

    def get_examscore(self, obj):
        return obj.active_trial.exam_score if obj.active_trial else 0

    def get_student_score(self, obj):
        return obj.active_trial.score if obj.active_trial else 0

    def get_trials(self, obj):
        return ResultTrialSerializer(obj.trials.all(), many=True).data


class FlattenedExamResultSerializer(serializers.ModelSerializer):
    exam_id = serializers.IntegerField(source="id")
    exam_title = serializers.CharField(source="title")
    exam_description = serializers.SerializerMethodField()
    exam_number_of_allowed_trials = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    unit_title = serializers.SerializerMethodField()
    passing_percent = serializers.FloatField()
    exam_time_limit = serializers.IntegerField(source="time_limit")
    examscore = serializers.SerializerMethodField()
    student_score = serializers.SerializerMethodField()
    trial = serializers.SerializerMethodField()
    is_trials_finished = serializers.SerializerMethodField()
    issucceeded = serializers.SerializerMethodField()
    trials = serializers.SerializerMethodField()
    result_id = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            "result_id",
            "exam_id",
            "exam_title",
            "exam_description",
            "course_title",
            "unit_title",
            "passing_percent",
            "exam_time_limit",
            "examscore",
            "student_score",
            "exam_number_of_allowed_trials",
            "trial",
            "is_trials_finished",
            "issucceeded",
            "trials",
        ]

    def get_course_title(self, obj):
        return obj.course.name if obj.course else None

    def get_exam_description(self, obj):
        return None

    def get_exam_number_of_allowed_trials(self, obj):
        if not hasattr(self, '_main_exam_daily_limit'):
            self._main_exam_daily_limit = ExamConfig.load().max_trials_per_day
        return self._main_exam_daily_limit

    def get_unit_title(self, obj):
        return obj.unit.name if obj.unit else None

    def _result(self, obj):
        student_id = self.context.get("student_id")
        if not student_id:
            return None
        return Result.objects.filter(exam=obj, student_id=student_id).prefetch_related("trials").first()

    def get_result_id(self, obj):
        result = self._result(obj)
        return result.id if result else None

    def get_examscore(self, obj):
        result = self._result(obj)
        return result.active_trial.exam_score if result and result.active_trial else 0

    def get_student_score(self, obj):
        result = self._result(obj)
        return result.active_trial.score if result and result.active_trial else 0

    def get_trial(self, obj):
        result = self._result(obj)
        return result.trial if result else None

    def get_is_trials_finished(self, obj):
        result = self._result(obj)
        return result.is_trials_finished if result else False

    def get_issucceeded(self, obj):
        result = self._result(obj)
        return result.is_succeeded if result else False

    def get_trials(self, obj):
        result = self._result(obj)
        return ResultTrialSerializer(result.trials.all(), many=True).data if result else []


class FlattenedStudentResultSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    student_user__username = serializers.CharField(source="user.username")
    student_name = serializers.CharField(source="name")
    student_parent_phone = serializers.CharField(source="parent_phone", allow_null=True)
    student_code = serializers.CharField(source="code", allow_null=True)
    student_gender = serializers.CharField(source="user.gender")
    exam_id = serializers.SerializerMethodField()
    exam_title = serializers.SerializerMethodField()
    examscore = serializers.SerializerMethodField()
    student_score = serializers.SerializerMethodField()
    trial = serializers.SerializerMethodField()
    is_trials_finished = serializers.SerializerMethodField()
    issucceeded = serializers.SerializerMethodField()
    trials = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "student_user__username",
            "student_name",
            "student_parent_phone",
            "student_code",
            "student_gender",
            "exam_id",
            "exam_title",
            "examscore",
            "student_score",
            "trial",
            "is_trials_finished",
            "issucceeded",
            "trials",
        ]

    def _result(self, obj):
        exam_id = self.context.get("exam_id")
        if not exam_id:
            return None
        return Result.objects.filter(student=obj, exam_id=exam_id).prefetch_related("trials").first()

    def get_exam_id(self, obj):
        result = self._result(obj)
        return result.exam_id if result else None

    def get_exam_title(self, obj):
        result = self._result(obj)
        return result.exam.title if result else None

    def get_examscore(self, obj):
        result = self._result(obj)
        return result.active_trial.exam_score if result and result.active_trial else 0

    def get_student_score(self, obj):
        result = self._result(obj)
        return result.active_trial.score if result and result.active_trial else 0

    def get_trial(self, obj):
        result = self._result(obj)
        return result.trial if result else None

    def get_is_trials_finished(self, obj):
        result = self._result(obj)
        return result.is_trials_finished if result else False

    def get_issucceeded(self, obj):
        result = self._result(obj)
        return result.is_succeeded if result else False

    def get_trials(self, obj):
        result = self._result(obj)
        return ResultTrialSerializer(result.trials.all(), many=True).data if result else []


class StudentDidNotTakeExamSerializer(serializers.ModelSerializer):
    student_user__username = serializers.CharField(source="user.username")
    student_name = serializers.CharField(source="name")
    student_parent_phone = serializers.CharField(source="parent_phone", allow_null=True)
    student_gender = serializers.CharField(source="user.gender")
    course_subscribed_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = Student
        fields = ["id", "student_user__username", "student_name", "student_parent_phone", "student_gender", "code", "course_subscribed_at"]


class CombinedStudentResultSerializer(serializers.ModelSerializer):
    result = BriefedResultSerializer(source="result_set", many=True, read_only=True)
    gender = serializers.CharField(source="user.gender", read_only=True)

    class Meta:
        model = Student
        fields = ["id", "name", "gender", "parent_phone", "code", "result"]


class ExamQuestionSerializer(serializers.ModelSerializer):
    exam_question_id = serializers.IntegerField(source="id", read_only=True)
    question = QuestionSerializer(read_only=True)

    class Meta:
        model = ExamQuestion
        fields = ["id", "exam_question_id", "exam", "question", "is_active", "order", "created"]
        read_only_fields = ["id", "exam_question_id", "created"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("question"):
            data["question"]["exam_question_id"] = data["exam_question_id"]
        return data
