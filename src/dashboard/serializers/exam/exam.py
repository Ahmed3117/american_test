from django.utils import timezone
from rest_framework import serializers

from course.models import Course, Unit
from exam.models import (
    AdminQuestionBank,
    Answer,
    EssaySubmission,
    Exam,
    ExamConfig,
    ExamModel,
    ExamQuestion,
    Question,
    QuestionCategory,
    QuestionImage,
    RandomExamBank,
    RelatedToChoices,
    Result,
    ResultTrial,
    TempExamAllowedTimes,
    Year,
)
from student.models import Student
from exam.serializer_fields import StoredFileField, stored_file_url


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
            for i, answer_data in enumerate(answers_data):
                raw_id = raw_answers[i].get("id") if i < len(raw_answers) else None
                if raw_id and instance.answers.filter(id=raw_id).exists():
                    Answer.objects.filter(id=raw_id, question=instance).update(**answer_data)
                    processed_ids.append(int(raw_id))
                else:
                    answer = Answer.objects.create(question=instance, **answer_data)
                    processed_ids.append(answer.id)
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


class QuestionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionCategory
        fields = ["id", "title"]


class YearSerializer(serializers.ModelSerializer):
    class Meta:
        model = Year
        fields = ["id", "value"]


class EssaySubmissionSerializer(serializers.ModelSerializer):
    answer_file_url = serializers.SerializerMethodField()
    student_gender = serializers.CharField(source="student.user.gender", read_only=True)

    class Meta:
        model = EssaySubmission
        fields = [
            "id",
            "student",
            "student_gender",
            "exam",
            "question",
            "answer_text",
            "answer_file",
            "answer_file_url",
            "score",
            "is_scored",
            "created",
            "result_trial",
        ]
        extra_kwargs = {"answer_file": {"write_only": True, "required": False}}

    def get_answer_file_url(self, obj):
        if not obj.answer_file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.answer_file.url) if request else obj.answer_file.url

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["student"] = instance.student.name
        data["exam"] = instance.exam.title
        data["question"] = instance.question.text
        data["question_points"] = instance.question.points
        data["question_explanation_text"] = instance.question.explanation_text
        data["question_explanation_video_url"] = stored_file_url(
            instance.question.explanation_video_url
        )
        data["question_explanation_recorded_audio"] = instance.question.explanation_recorded_audio.url if instance.question.explanation_recorded_audio else None
        data["question_comment"] = instance.question.comment
        data["question_image"] = (
            instance.question.images.first().image.url
            if instance.question.images.first()
            else None
        )
        data["question_images"] = [
            {"id": qi.id, "image": qi.image.url}
            for qi in instance.question.images.all()
        ]
        return data


class RandomExamBankSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = RandomExamBank
        fields = ["exam", "questions"]


class ExamModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamModel
        fields = "__all__"


class ResultTrialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultTrial
        fields = [
            "id",
            "result",
            "trial",
            "score",
            "exam_score",
            "exam_model",
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
        if not hasattr(self, '_main_exam_daily_limit'):
            self._main_exam_daily_limit = ExamConfig.load().max_trials_per_day
        return self._main_exam_daily_limit

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


class CopyExamSerializer(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), required=False, allow_null=True)
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=False, allow_null=True)
    related_to = serializers.ChoiceField(choices=RelatedToChoices.choices)

    def validate(self, attrs):
        if attrs["related_to"] == RelatedToChoices.COURSE and not attrs.get("course"):
            raise serializers.ValidationError("Course is required for course exam copies.")
        if attrs["related_to"] == RelatedToChoices.UNIT and not attrs.get("unit"):
            raise serializers.ValidationError("Unit is required for unit exam copies.")
        if attrs.get("unit"):
            attrs["course"] = attrs["unit"].course
        return attrs


class ExamQuestionReorderSerializer(serializers.Serializer):
    exam_question = serializers.IntegerField(help_text="ID of the ExamQuestion instance.")
    new_order = serializers.IntegerField(help_text="The new order value.")

    def validate_exam_question(self, value):
        if not ExamQuestion.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"ExamQuestion with ID {value} does not exist.")
        return value

    def validate_new_order(self, value):
        if value < 1:
            raise serializers.ValidationError("New order must be a positive integer.")
        return value


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


class TempExamAllowedTimesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TempExamAllowedTimes
        fields = ["number_of_allowedtempexams_per_day"]

    def validate_number_of_allowedtempexams_per_day(self, value):
        if value < 0:
            raise serializers.ValidationError("Number of allowed temp exams per day cannot be negative.")
        return value


class AdminQuestionBankSerializer(serializers.ModelSerializer):
    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all(), write_only=True)
    question_details = QuestionSerializer(source="question", read_only=True)
    question_text = serializers.CharField(source="question.text", read_only=True)
    question_type = serializers.CharField(source="question.question_type", read_only=True)
    question_points = serializers.IntegerField(source="question.points", read_only=True)

    class Meta:
        model = AdminQuestionBank
        fields = ["id", "question", "question_details", "question_text", "question_type", "question_points", "created"]
        read_only_fields = ["id", "created"]


class AddExamQuestionsSerializer(serializers.Serializer):
    question_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)

    def validate_question_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        existing_count = Question.objects.filter(id__in=unique_ids).count()
        if existing_count != len(unique_ids):
            raise serializers.ValidationError("One or more questions do not exist.")
        return unique_ids
