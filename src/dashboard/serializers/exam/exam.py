from rest_framework import serializers

from exam.models import (
    Answer,
    Exam,
    ExamConfig,
    ExamMode,
    ExamQuestion,
    Question,
    QuestionCategory,
    QuestionImage,
    Result,
    ResultTrial,
    StudentAccessType,
    StudentExamQuotaOverride,
    Year,
)
from student.models import Student
from exam.serializer_fields import StoredFileField
from exam.services import (
    effective_exam_limits,
    exam_quota_status,
)


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
    student_academic_year = serializers.CharField(source='student.user.academic_year', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    category_names = serializers.SerializerMethodField()
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
            "student_academic_year",
            "title",
            "course",
            "course_name",
            "categories",
            "category_names",
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

    def get_category_names(self, obj):
        return [category.title for category in obj.categories.all()]


class ExamConfigSerializer(serializers.ModelSerializer):
    student_type = serializers.ChoiceField(
        choices=StudentAccessType.choices,
        required=True,
    )
    max_questions_per_exam = serializers.IntegerField(min_value=1)

    class Meta:
        model = ExamConfig
        fields = [
            'id',
            'student_type',
            'max_trials_per_day',
            'max_trials_per_week',
            'max_trials_per_month',
            'max_questions_per_exam',
        ]
        read_only_fields = ['id']

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


class StudentExamLimitSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source='id', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    student_name = serializers.CharField(source='name', read_only=True)
    student_phone = serializers.CharField(source='user.username', read_only=True)
    student_academic_year = serializers.CharField(source='user.academic_year', read_only=True)
    limits = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'student_id',
            'user_id',
            'student_name',
            'student_phone',
            'student_academic_year',
            'limits',
        ]

    def _configs(self):
        if not hasattr(self, '_config_cache'):
            self._config_cache = {
                config.student_type: config for config in ExamConfig.objects.all()
            }
            for student_type in StudentAccessType.values:
                if student_type not in self._config_cache:
                    self._config_cache[student_type] = ExamConfig.load(student_type)
        return self._config_cache

    @staticmethod
    def _overrides(obj):
        return {
            (override.exam_type, override.student_type): override
            for override in obj.exam_quota_overrides.all()
        }

    def get_limits(self, obj):
        configs = self._configs()
        overrides = self._overrides(obj)
        include_usage = self.context.get('include_usage', False)
        rows = []
        for exam_type in ExamMode.values:
            for student_type in StudentAccessType.values:
                override = overrides.get((exam_type, student_type))
                custom = {
                    'daily': getattr(override, 'max_trials_per_day', None),
                    'weekly': getattr(override, 'max_trials_per_week', None),
                    'monthly': getattr(override, 'max_trials_per_month', None),
                }
                config = configs[student_type]
                effective = {
                    'daily': config.max_trials_per_day if custom['daily'] is None else custom['daily'],
                    'weekly': config.max_trials_per_week if custom['weekly'] is None else custom['weekly'],
                    'monthly': config.max_trials_per_month if custom['monthly'] is None else custom['monthly'],
                    'max_questions_per_exam': config.max_questions_per_exam,
                }
                row = {
                    'exam_type': exam_type,
                    'student_type': student_type,
                    'custom_limits': custom,
                    'effective_limits': effective,
                    'uses_custom_trial_limits': any(
                        value is not None for value in custom.values()
                    ),
                }
                if include_usage:
                    quota = exam_quota_status(
                        obj,
                        exam_type=exam_type,
                        access_type=student_type,
                    )
                    row.update({
                        'usage': quota['usage'],
                        'remaining': quota['remaining'],
                        'reached_limits': quota['reached_limits'],
                        'can_start': quota['can_start'],
                    })
                rows.append(row)
        return rows


class StudentExamQuotaOverrideUpdateSerializer(serializers.Serializer):
    exam_type = serializers.ChoiceField(choices=ExamMode.choices)
    student_type = serializers.ChoiceField(choices=StudentAccessType.choices)
    max_trials_per_day = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )
    max_trials_per_week = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )
    max_trials_per_month = serializers.IntegerField(
        min_value=0, allow_null=True, required=False
    )

    def validate(self, attrs):
        limit_fields = (
            'max_trials_per_day',
            'max_trials_per_week',
            'max_trials_per_month',
        )
        if not any(field in attrs for field in limit_fields):
            raise serializers.ValidationError(
                'Send at least one daily, weekly, or monthly override.'
            )
        student = self.context['student']
        override = StudentExamQuotaOverride.objects.filter(
            student=student,
            exam_type=attrs['exam_type'],
            student_type=attrs['student_type'],
        ).first()
        config = ExamConfig.load(attrs['student_type'])
        custom = {
            'daily': attrs.get(
                'max_trials_per_day', getattr(override, 'max_trials_per_day', None)
            ),
            'weekly': attrs.get(
                'max_trials_per_week', getattr(override, 'max_trials_per_week', None)
            ),
            'monthly': attrs.get(
                'max_trials_per_month', getattr(override, 'max_trials_per_month', None)
            ),
        }
        effective = {
            'daily': config.max_trials_per_day if custom['daily'] is None else custom['daily'],
            'weekly': config.max_trials_per_week if custom['weekly'] is None else custom['weekly'],
            'monthly': config.max_trials_per_month if custom['monthly'] is None else custom['monthly'],
        }
        if effective['daily'] > effective['weekly']:
            raise serializers.ValidationError({
                'max_trials_per_week': 'The effective weekly limit must be at least the effective daily limit.'
            })
        if effective['weekly'] > effective['monthly']:
            raise serializers.ValidationError({
                'max_trials_per_month': 'The effective monthly limit must be at least the effective weekly limit.'
            })
        return attrs

    def save(self, **kwargs):
        student = self.context['student']
        exam_type = self.validated_data['exam_type']
        student_type = self.validated_data['student_type']
        override, _ = StudentExamQuotaOverride.objects.get_or_create(
            student=student,
            exam_type=exam_type,
            student_type=student_type,
        )
        for field in (
            'max_trials_per_day',
            'max_trials_per_week',
            'max_trials_per_month',
        ):
            if field in self.validated_data:
                setattr(override, field, self.validated_data[field])
        if all(
            getattr(override, field) is None
            for field in (
                'max_trials_per_day',
                'max_trials_per_week',
                'max_trials_per_month',
            )
        ):
            override.delete()
            return None
        override.save()
        return override


class QuestionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionCategory
        fields = ["id", "title", "course"]


class YearSerializer(serializers.ModelSerializer):
    class Meta:
        model = Year
        fields = ["id", "value"]


class ResultTrialSerializer(serializers.ModelSerializer):
    student_academic_year = serializers.CharField(source="result.student.user.academic_year", read_only=True)

    class Meta:
        model = ResultTrial
        fields = [
            "id",
            "result",
            "student_academic_year",
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
    student_academic_year = serializers.CharField(source="student.user.academic_year", read_only=True)
    parent_phone = serializers.SerializerMethodField()
    student_started_exam_at = serializers.SerializerMethodField()
    student_submitted_exam_at = serializers.SerializerMethodField()
    submit_type = serializers.SerializerMethodField()
    has_unsubscribed_submission = serializers.BooleanField(read_only=True)
    submitted_by_unsubscribed_user = serializers.SerializerMethodField()
    quota_access_type = serializers.SerializerMethodField()
    effective_trial_limits = serializers.SerializerMethodField()
    trial_usage = serializers.SerializerMethodField()
    trial_remaining = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()

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
            "student_academic_year",
            "parent_phone",
            "student_started_exam_at",
            "student_submitted_exam_at",
            "submit_type",
            "has_unsubscribed_submission",
            "submitted_by_unsubscribed_user",
            "quota_access_type",
            "effective_trial_limits",
            "trial_usage",
            "trial_remaining",
            "can_start",
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
        return self._quota(obj)['limits']['daily']

    def _access_type(self, obj):
        trial = self._active_trial(obj)
        if trial and trial.submitted_by_unsubscribed_user:
            return StudentAccessType.UNSUBSCRIBED
        return StudentAccessType.SUBSCRIBED

    def _quota(self, obj):
        if not hasattr(self, '_quota_cache'):
            self._quota_cache = {}
        access_type = self._access_type(obj)
        key = (obj.student_id, access_type)
        if key not in self._quota_cache:
            self._quota_cache[key] = exam_quota_status(
                obj.student,
                exam_type=ExamMode.MAIN,
                access_type=access_type,
            )
        return self._quota_cache[key]

    def get_quota_access_type(self, obj):
        return self._access_type(obj)

    def get_effective_trial_limits(self, obj):
        return self._quota(obj)['limits']

    def get_trial_usage(self, obj):
        return self._quota(obj)['usage']

    def get_trial_remaining(self, obj):
        return self._quota(obj)['remaining']

    def get_can_start(self, obj):
        return self._quota(obj)['can_start']

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
    student_academic_year = serializers.CharField(source="user.academic_year", read_only=True)
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
            "student_academic_year",
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
        result = self._result(obj)
        trial = result.active_trial if result else None
        access_type = (
            StudentAccessType.UNSUBSCRIBED
            if trial and trial.submitted_by_unsubscribed_user
            else StudentAccessType.SUBSCRIBED
        )
        return effective_exam_limits(
            obj.student,
            ExamMode.MAIN,
            access_type,
        )['limits']['daily']

    def _result(self, obj):
        student_id = self.context.get("student_id")
        if not student_id:
            return None
        return Result.objects.filter(exam=obj, student_id=student_id).select_related(
            "student__user"
        ).prefetch_related("trials").first()

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


class CombinedStudentResultSerializer(serializers.ModelSerializer):
    result = BriefedResultSerializer(source="result_set", many=True, read_only=True)
    gender = serializers.CharField(source="user.gender", read_only=True)
    academic_year = serializers.CharField(source="user.academic_year", read_only=True)

    class Meta:
        model = Student
        fields = ["id", "name", "gender", "academic_year", "parent_phone", "code", "result"]


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
