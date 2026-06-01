from rest_framework import serializers

from course.models import Course, Unit
from .models import Answer, Exam, ExamType, Question, Result, StudentBank, TempExam, AdminQuestionBank, StudentCreatedExam
from student.models import Student,StudentFavorite
from django.contrib.contenttypes.models import ContentType

class ExamSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    related_name = serializers.CharField(source='get_related_name', read_only=True)
    number_of_questions = serializers.SerializerMethodField()
    has_passed_exam = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    favorite_id = serializers.SerializerMethodField()
    class Meta:
        model = Exam
        fields = [
            'id',
            'title',
            'description',
            'number_of_questions',
            'time_limit',
            'score',
            'passing_percent',
            'start',
            'end',
            'time_limit',
            'status',
            'related_name',
            'order',
            'is_active',
            'show_answers_after_finish',
            'is_depends',
            'number_of_questions',
            'has_passed_exam',
            'is_favorite',
            'favorite_id',
        ]
        
    def get_number_of_questions(self,obj):
        if obj.type == ExamType.RANDOM:
            return 'not_calculatable'
        elif obj.type in [ExamType.MANUAL, ExamType.BANK]:
            return obj.exam_questions.count()
        else:
            return 0
    
    def get_has_passed_exam(self, obj):
        request = self.context.get("request")
        try:
            student = request.user.student
        except AttributeError:
            return True
        related_course = obj.course or (obj.unit.course if obj.unit else None)
        if not related_course:
            return True

        # Get all dependent exams in the same course with a lower order
        dependent_exams = Exam.objects.filter(
            course=related_course,
            order__lt=obj.order,
            is_depends=True
        )

        if not dependent_exams.exists():
            return True

        for exam in dependent_exams:
            result = Result.objects.filter(student=student, exam=exam).first()
            if not result or not result.is_succeeded:
                return False

        return True

    
    
    def get_is_favorite(self, obj):
        request = self.context.get("request")
        student = getattr(request.user, "student", None)
        if not student:
            return False
        content_type = ContentType.objects.get_for_model(Exam)
        return StudentFavorite.objects.filter(student=student, content_type=content_type, object_id=obj.id).exists()


    def get_favorite_id(self, obj):
        request = self.context.get("request")
        student = getattr(request.user, "student", None)
        if not student:
            return None
        content_type = ContentType.objects.get_for_model(Exam)
        favorite = StudentFavorite.objects.filter(student=student, content_type=content_type, object_id=obj.id).first()
        return favorite.id if favorite else None
    
    
    

class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'text', 'image']

class QuestionSerializerWithoutCorrectAnswer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = ['id', 'text', 'explanation_text', 'explanation_video_url', 'explanation_recorded_audio', 'image', 'points', 'difficulty', 'category', 'course', 'unit', 'is_active', 'answers', 'question_type']

class AnswerSerializerWithCorrectAnswer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ['id', 'text', 'image','is_correct']

class QuestionSerializerWithCorrectAnswer(serializers.ModelSerializer):
    answers = AnswerSerializerWithCorrectAnswer(many=True, required=False)

    class Meta:
        model = Question
        fields = ['id', 'text', 'explanation_text', 'explanation_video_url', 'explanation_recorded_audio', 'image', 'points', 'difficulty', 'category', 'course', 'unit', 'is_active', 'answers', 'question_type']


class StudentExamResultSerializer(serializers.ModelSerializer):
    result_id = serializers.IntegerField(source='id')
    exam_id = serializers.IntegerField(source='exam.id')
    exam_title = serializers.CharField(source='exam.title')
    # exam_description = serializers.CharField(source='exam.description')  # Commented out
    # exam_related_to = serializers.CharField(source='exam.related_to')  # Commented out
    # exam_unit = serializers.IntegerField(source='exam.unit.id', allow_null=True)  # Commented out
    # exam_course = serializers.SerializerMethodField()  # Commented out
    # number_of_allowed_trials = serializers.IntegerField(source='exam.number_of_allowed_trials')  # Commented out
    # trials = serializers.IntegerField(source='trial')  # Commented out
    # trials_finished = serializers.BooleanField(source='is_trials_finished')  # Commented out
    # passing_percent = serializers.IntegerField(source='exam.passing_percent')  # Commented out
    allowed_to_show_result = serializers.BooleanField(source='is_allowed_to_show_result')  # Commented out
    allowed_to_show_answers = serializers.BooleanField(source='is_allowed_to_show_answers')  # Commented out
    # added_at = serializers.DateTimeField(source='added')  # Commented out
    # start = serializers.DateTimeField(source='exam.start')  # Commented out
    # end = serializers.DateTimeField(source='exam.end')  # Commented out
    # student_id = serializers.IntegerField(source='student.id')  # Commented out
    # student_name = serializers.CharField(source='student.name')  # Commented out
    # student_phone = serializers.CharField(source='student.user.username')  # Commented out
    # parent_phone = serializers.CharField(source='student.parent_phone')  # Commented out
    # jwt_token = serializers.CharField(source='student.jwt_token')  # Commented out
    number_of_questions = serializers.SerializerMethodField()
    exam_score = serializers.SerializerMethodField()
    student_score = serializers.SerializerMethodField()
    is_succeeded = serializers.SerializerMethodField()
    # correct_questions_count = serializers.SerializerMethodField()  # Commented out
    # incorrect_questions_count = serializers.SerializerMethodField()  # Commented out
    # insolved_questions_count = serializers.SerializerMethodField()  # Commented out
    student_started_exam_at = serializers.SerializerMethodField()
    student_submitted_exam_at = serializers.SerializerMethodField()
    # submit_type = serializers.SerializerMethodField()  # Commented out
    last_trials = serializers.SerializerMethodField()

    class Meta:
        model = Result
        fields = [
            'result_id', 
            'exam_id', 
            'exam_title', 
            # 'exam_description',  # Commented out
            # 'exam_related_to',  # Commented out
            # 'exam_unit',  # Commented out
            # 'exam_course',  # Commented out
            'exam_score', 
            'student_score',
            # 'trials',  # Commented out
            # 'trials_finished',  # Commented out
            # 'number_of_allowed_trials',  # Commented out
            'is_succeeded',
            # 'correct_questions_count',  # Commented out
            # 'incorrect_questions_count',  # Commented out
            # 'insolved_questions_count',  # Commented out
            'number_of_questions',
            'allowed_to_show_result',  # Commented out
            'allowed_to_show_answers',  # Commented out
            # 'passing_percent',  # Commented out
            # 'added_at',  # Commented out
            # 'start',  # Commented out
            # 'end',  # Commented out
            # 'student_id',  # Commented out
            # 'student_name',  # Commented out
            # 'student_phone',  # Commented out
            # 'parent_phone',  # Commented out
            # 'jwt_token',  # Commented out
            'student_started_exam_at',
            'student_submitted_exam_at',
            # 'submit_type',  # Commented out
            'last_trials'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_trials = {}
        # self._submission_counts = {}  # Commented out as not needed

    # def get_exam_course(self, obj):  # Commented out
    #     return obj.exam.get_related_course()

    def get_last_trials(self, obj):
        """Return the last 3 trials for this result"""
        if not obj.is_allowed_to_show_result:
            return "غير مسموح بعرض النتائج بعد"
            
        # Get all trials ordered by trial number (descending)
        all_trials = obj.trials.all().order_by('-trial')
        
        # Take up to 3 most recent trials
        # last_trials = all_trials[:3]
        last_trials = all_trials
        
        # Serialize the trial data
        return [{
            'id': trial.id,
            'trial_number': trial.trial,
            'score': trial.score,
            'exam_score': trial.exam_score,
            'started_at': trial.student_started_exam_at,
            'submitted_at': trial.student_submitted_exam_at,
            # 'submit_type': trial.submit_type,  # Commented out
            'is_passed': trial.score >= (obj.exam.passing_percent / 100) * trial.exam_score
        } for trial in last_trials]

    def get_exam_score(self, obj):
        active_trial = self._get_active_trial(obj)
        return active_trial.exam_score if active_trial else 0

    def get_student_score(self, obj):
        if not obj.is_allowed_to_show_result:
            return "غير مسموح بعد"
        active_trial = self._get_active_trial(obj)
        return active_trial.score if active_trial else 0

    def get_is_succeeded(self, obj):
        if not obj.is_allowed_to_show_result:
            return "غير مسموح بعد"
        active_trial = self._get_active_trial(obj)
        if active_trial:
            return active_trial.score >= (obj.exam.passing_percent / 100) * active_trial.exam_score
        return False

    # def get_correct_questions_count(self, obj):  # Commented out
    #     if not obj.is_allowed_to_show_result:
    #         return "not_allowed_yet"
    #     return self._get_submission_counts(obj)['correct']

    # def get_incorrect_questions_count(self, obj):  # Commented out
    #     if not obj.is_allowed_to_show_result:
    #         return "not_allowed_yet"
    #     return self._get_submission_counts(obj)['incorrect']

    # def get_insolved_questions_count(self, obj):  # Commented out
    #     if not obj.is_allowed_to_show_result:
    #         return "not_allowed_yet"
    #     return self._get_submission_counts(obj)['unsolved']
    
    def get_number_of_questions(self, obj):
        if obj.exam.type == ExamType.RANDOM and obj.exam_model:
            return getattr(obj.exam_model, 'model_questions', []).count() if hasattr(obj.exam_model, 'model_questions') else 0
        else:
            return len([eq for eq in obj.exam.exam_questions.all() if eq.question.is_active])

    def get_student_started_exam_at(self, obj):
        active_trial = self._get_active_trial(obj)
        return active_trial.student_started_exam_at if active_trial else None

    def get_student_submitted_exam_at(self, obj):
        active_trial = self._get_active_trial(obj)
        return active_trial.student_submitted_exam_at if active_trial else None

    # def get_submit_type(self, obj):  # Commented out
    #     active_trial = self._get_active_trial(obj)
    #     return active_trial.submit_type if active_trial else None

    def _get_active_trial(self, obj):
        if obj.id not in self._active_trials:
            self._active_trials[obj.id] = obj.active_trial
        return self._active_trials[obj.id]

    # def _get_submission_counts(self, obj):  # Commented out
    #     if obj.id not in self._submission_counts:
    #         active_trial = self._get_active_trial(obj)
    #         if active_trial and obj.is_allowed_to_show_result:
    #             submissions = [
    #                 sub for sub in obj.exam.submissions.all()
    #                 if sub.result_trial_id == active_trial.id
    #             ]
    #             counts = {
    #                 'correct': sum(1 for sub in submissions if sub.is_correct),
    #                 'incorrect': sum(1 for sub in submissions if not sub.is_correct),
    #                 'unsolved': sum(1 for sub in submissions if not sub.is_solved)
    #             }
    #         else:
    #             counts = {'correct': 0, 'incorrect': 0, 'unsolved': 0}
    #         self._submission_counts[obj.id] = counts
    #     return self._submission_counts[obj.id]




#^ < ==============================[ <- Student Temp Exams -> ]============================== > ^#



class StudentBankSerializer(serializers.ModelSerializer):
    question = QuestionSerializerWithCorrectAnswer(read_only=True)
    course = serializers.CharField(source='question.course.id', read_only=True, allow_null=True)
    unit = serializers.CharField(source='question.unit.id', read_only=True, allow_null=True)

    class Meta:
        model = StudentBank
        fields = ['id', 'question', 'add_reason', 'is_solved_now', 'created', 'course', 'unit']

class TempExamSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), required=False, allow_null=True)
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=False, allow_null=True)
    selected_questions_type = serializers.ChoiceField(
        choices=['solved', 'not_solved', None],
        allow_null=True,
        required=False
    )

    class Meta:
        model = TempExam
        fields = ['id', 'student', 'course', 'unit', 'number_of_questions', 'time_limit', 'created', 'result', 'selected_questions_type']


class AdminQuestionBankSerializer(serializers.ModelSerializer):
    # Accept question ID on create
    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all(), write_only=True)
    # Return full question with answers (including is_correct) on read
    question_details = QuestionSerializerWithCorrectAnswer(source='question', read_only=True)
    # Keep existing convenience read-only fields
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    question_points = serializers.IntegerField(source='question.points', read_only=True)
    question_explanation_text = serializers.CharField(source='question.explanation_text', read_only=True, allow_null=True)
    question_explanation_video_url = serializers.URLField(source='question.explanation_video_url', read_only=True, allow_null=True)
    question_explanation_recorded_audio = serializers.FileField(source='question.explanation_recorded_audio', read_only=True, allow_null=True)

    class Meta:
        model = AdminQuestionBank
        fields = [
            'id', 'question', 'question_details', 'question_text', 'question_type', 'question_points',
            'question_explanation_text', 'question_explanation_video_url', 'question_explanation_recorded_audio',
            'created'
        ]


class StudentCreatedExamSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    total_questions = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentCreatedExam
        fields = [
            'id', 'student', 'course', 'course_name', 'unit', 'unit_name',
            'number_of_mcq_questions', 'number_of_essay_questions', 'total_questions',
            'time_limit', 'exam_score', 'result', 'percentage', 'created'
        ]
        read_only_fields = ['student', 'exam_score']
    
    def get_total_questions(self, obj):
        return obj.number_of_mcq_questions + obj.number_of_essay_questions
    
    def get_percentage(self, obj):
        if obj.result is not None and obj.exam_score > 0:
            return (obj.result / obj.exam_score) * 100
        return 0
