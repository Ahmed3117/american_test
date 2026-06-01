from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
from course.models import Course, Unit
from student.models import Student
from django.utils.timezone import now
import random


# Choices
class RelatedToChoices(models.TextChoices):
    COURSE = 'COURSE', _('Course')
    UNIT = 'UNIT', _('Unit')

class DifficultyLevel(models.TextChoices):
    EASY = 'EASY', _('Easy')
    MEDIUM = 'MEDIUM', _('Medium')
    HARD = 'HARD', _('Hard')

class ExamType(models.TextChoices):
    RANDOM = 'RANDOM', _('Random')
    MANUAL = 'MANUAL', _('Manual')
    BANK = 'BANK', _('Pic From the Bank')

class PonusOption(models.TextChoices):
    STUDENT_LAST_TRIAL_SCORE = 'student_last_trial_score', _('Student Last Trial Score')
    FIXED_PONUS = 'fixed_ponus', _('Fixed Ponus')

class QuestionType(models.TextChoices):
    MCQ = 'MCQ', _('Multiple Choice Question')
    ESSAY = 'ESSAY', _('Essay Question')

class Exam(models.Model):
    title = models.CharField(max_length=120)
    description = models.TextField(null=True, blank=True)
    related_to = models.CharField(max_length=10, choices=RelatedToChoices.choices)

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='exams', null=True, blank=True
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, related_name='exams', null=True, blank=True
    )
    
    number_of_questions = models.PositiveIntegerField(default=1)
    time_limit = models.PositiveIntegerField(help_text="Time limit in minutes")
    score = models.FloatField(default=0.0)
    passing_percent = models.PositiveIntegerField(default=50)
    created = models.DateTimeField(auto_now_add=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    number_of_allowed_trials = models.PositiveIntegerField(default=1)
    
    type = models.CharField(
        max_length=10, choices=ExamType.choices, default=ExamType.MANUAL
    )
    
    easy_questions_count = models.PositiveIntegerField(default=0)
    medium_questions_count = models.PositiveIntegerField(default=0)
    hard_questions_count = models.PositiveIntegerField(default=0)
    show_answers_after_finish = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    allow_show_results_at = models.DateTimeField(default=timezone.now)
    allow_show_answers_at = models.DateTimeField(null=True, blank=True)
    is_depends = models.BooleanField(default=False)
    show_questions_in_random = models.BooleanField(default=True)
    ponus = models.IntegerField(default=0)
    ponus_option = models.CharField(max_length=30, choices=PonusOption.choices, null=True, blank=True)

    def clean(self):
        super().clean()
        if self.easy_questions_count + self.medium_questions_count + self.hard_questions_count > self.number_of_questions:
            raise ValidationError(_("The total count of questions cannot exceed the number of questions."))
        if self.related_to == RelatedToChoices.COURSE and not self.course:
            raise ValidationError(_("Course is required when related to course."))
        if self.related_to == RelatedToChoices.UNIT and not self.unit:
            raise ValidationError(_("Unit is required when related to unit."))
        if self.related_to == RelatedToChoices.COURSE and self.unit:
            raise ValidationError(_("A course exam cannot also target a unit."))
        if self.type == ExamType.RANDOM:
            self.validate_random_exam()

    def validate_random_exam(self):
        if self.related_to == RelatedToChoices.COURSE:
            related_queryset = Question.objects.filter(course=self.course)
        elif self.related_to == RelatedToChoices.UNIT:
            related_queryset = Question.objects.filter(unit=self.unit)
        else:
            raise ValidationError(_("Exam must be related to either a course or a unit."))

        easy_count = related_queryset.filter(difficulty=DifficultyLevel.EASY).count()
        medium_count = related_queryset.filter(difficulty=DifficultyLevel.MEDIUM).count()
        hard_count = related_queryset.filter(difficulty=DifficultyLevel.HARD).count()

        if self.easy_questions_count > easy_count:
            raise ValidationError(_("Not enough easy questions available for the selected count."))
        if self.medium_questions_count > medium_count:
            raise ValidationError(_("Not enough medium questions available for the selected count."))
        if self.hard_questions_count > hard_count:
            raise ValidationError(_("Not enough hard questions available for the selected count."))

    def status(self):
        if self.start > timezone.now():
            return 'soon'
        if self.end < timezone.now():
            return 'finished'
        return 'active'

    def get_related_name(self) -> str:
        if self.related_to == "COURSE" and self.course:
            return self.course.name
        if self.related_to == "UNIT" and self.unit:
            return self.unit.name
        return ""

    def get_related_course(self):
        if self.course:
            return self.course.id
        if self.unit:
            return self.unit.course_id
        return None

    def calculate_score(self):
        if self.type == ExamType.RANDOM:
            return 'not_calculatable'
        elif self.type in [ExamType.MANUAL, ExamType.BANK]:
            total_score = self.exam_questions.aggregate(total=Sum('question__points'))['total'] or 0
            return total_score
        else:
            return 0

    def calculate_number_of_questions(self):
        if self.type == ExamType.RANDOM:
            return 'not_calculatable'
        elif self.type in [ExamType.MANUAL, ExamType.BANK]:
            return self.exam_questions.count()
        else:
            return 0

    def save(self, *args, **kwargs):
        # assign related course before save
        if self.unit:
            self.course = self.unit.course
        elif self.related_to == RelatedToChoices.UNIT:
            self.course = None

        # auto-order logic
        if not self.pk and self.order == 0:
            if self.course:
                qs = Exam.objects.filter(course=self.course)
            else:
                qs = Exam.objects.none()

            last_order = qs.aggregate(models.Max("order"))["order__max"]
            self.order = (last_order or 0) + 1

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order','created']

class QuestionCategory(models.Model):
    title = models.CharField(max_length=200)
    
    def __str__(self):
        return self.title

class Question(models.Model):
    text = models.TextField()
    image = models.ImageField(upload_to='questions/', null=True, blank=True)
    points = models.PositiveIntegerField(default=1)
    difficulty = models.CharField(max_length=6, choices=DifficultyLevel.choices, default=DifficultyLevel.EASY)
    category = models.ForeignKey(
        QuestionCategory, on_delete=models.CASCADE, null=True, blank=True, db_index=True, related_name='categoryquestions'
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, null=True, blank=True, db_index=True, related_name='coursequestions'
    )
    unit = models.ForeignKey(
        Unit, on_delete=models.CASCADE, null=True, blank=True, db_index=True, related_name='unitquestions'
    )
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    question_type = models.CharField(max_length=5, choices=QuestionType.choices, default=QuestionType.MCQ)
    comment = models.TextField(null=True, blank=True)
    similar_questions = models.ManyToManyField(
        'self', 
        blank=True, 
        symmetrical=True,
        help_text="Questions that are similar to this question"
    )
    explanation_text = models.TextField(null=True, blank=True, help_text="Explanation text for the question")
    explanation_video_url = models.URLField(max_length=500, null=True, blank=True, help_text="Explanation video URL for the question")
    explanation_recorded_audio = models.FileField(upload_to='question_explanations/audio/', null=True, blank=True, help_text="Recorded audio explanation for the question")

    class Meta:
        indexes = [
            # Composite indexes for CreateTempExam performance
            models.Index(fields=['question_type', 'is_active']),
            models.Index(fields=['is_active', 'question_type']),
            # For similar question lookups and filtering
            models.Index(fields=['id', 'is_active', 'question_type']),
            # For course/unit/category based filtering with active/type checks
            models.Index(fields=['course', 'is_active', 'question_type']),
            models.Index(fields=['unit', 'is_active', 'question_type']),
            models.Index(fields=['category', 'is_active', 'question_type']),
        ]

    def save(self, *args, **kwargs):
        if self.unit:
            self.course = self.unit.course
        super().save(*args, **kwargs)

    def get_random_similar_question(self):
        """Get a random similar question, or return self if no similar questions exist"""
        similar_questions = list(self.similar_questions.filter(is_active=True, question_type=QuestionType.MCQ))
        if similar_questions:
            return random.choice(similar_questions)
        return self  # Return the question itself if no similar questions exist

    def __str__(self):
        return str(self.id) + " | " + str(self.question_type) + " | " + self.text

class Answer(models.Model):
    text = models.TextField()
    image = models.ImageField(upload_to='answers/', null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q: {self.question.text} | A: {self.text} | Correct: {self.is_correct}"

class ExamQuestion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='exam_questions')
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True , null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    order = models.PositiveIntegerField(default=1)
    class Meta:
        ordering = ['order', 'created']
    def __str__(self):
        return f"Exam: {self.exam.title} | Question: {self.question.text} | Active: {self.is_active}"

class RandomExamBank(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='random_exam_bank')
    questions = models.ManyToManyField(Question, related_name='random_exam_bank')

    def __str__(self):
        return f"Random Exam Bank for {self.exam.title}"

class ExamModel(models.Model):
    """Model to store different versions of a random exam"""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_models')
    title = models.CharField(max_length=120)
    created = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.exam.title} - Model: {self.title}"

class ExamModelQuestion(models.Model):
    """Questions assigned to a specific exam model"""
    exam_model = models.ForeignKey(ExamModel, on_delete=models.CASCADE, related_name='model_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('exam_model', 'question')
        indexes = [
            # For efficient filtering by exam model and active status
            models.Index(fields=['exam_model', 'is_active']),
            # For question-based lookups
            models.Index(fields=['question', 'is_active']),
        ]

class Submission(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='submissions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    is_solved = models.BooleanField(default=True)
    result_trial = models.ForeignKey('ResultTrial', on_delete=models.SET_NULL, related_name='submissions', null=True, blank=True)

    class Meta:
        indexes = [
            # For efficient lookups by student and exam combination
            models.Index(fields=['student', 'exam']),
            # For result trial related queries
            models.Index(fields=['result_trial', 'is_correct']),
            # For question performance analysis
            models.Index(fields=['question', 'is_correct']),
            # For student performance tracking
            models.Index(fields=['student', 'is_correct', 'is_solved']),
        ]
        # Ensure unique submission per student, exam, question, and result_trial
        unique_together = [['student', 'exam', 'question', 'result_trial']]

    def save(self, *args, **kwargs):
        # Automatically check if the answer is correct
        if self.selected_answer:
            self.is_correct = self.selected_answer.is_correct
        else:
            self.is_correct = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.result_trial} |{self.question.text} | Correct: {self.is_correct} | Solved: {self.is_solved}"


class EssaySubmission(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE,related_name='essaysubmissions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField()
    answer_file = models.FileField(upload_to='essay_submissions/', null=True, blank=True)  # New field
    score = models.FloatField(null=True, blank=True)
    is_scored = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    result_trial = models.ForeignKey('ResultTrial', on_delete=models.CASCADE, related_name='essay_submissions', null=True, blank=True)

    class Meta:
        # Ensure unique essay submission per student, exam, question, and result_trial
        unique_together = [['student', 'exam', 'question', 'result_trial']]

    def __str__(self):
        return f" {self.result_trial} | {self.question.text} | Score: {self.score}"

class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='results')
    trial = models.PositiveIntegerField(default=0)
    added = models.DateTimeField(auto_now_add=True)
    exam_model = models.ForeignKey(
        ExamModel, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        unique_together = ('student', 'exam')  # One result per student-exam combination.
        indexes = [
            # For efficient student-exam lookups
            models.Index(fields=['student', 'exam']),
            # For trial-based queries
            models.Index(fields=['trial', 'added']),
            # For date-based filtering
            models.Index(fields=['added', 'student']),
        ]

    @property
    def current_trial(self):
        """Fetch the ResultTrial for the current trial."""
        return self.trials.filter(trial=self.trial).first()

    @property
    def previous_trial(self):
        """Fetch the ResultTrial for the previous trial."""
        if self.trial > 1:
            return self.trials.filter(trial=self.trial - 1).first()
        return None

    @property
    def active_trial(self):
        """
        Fetch the active ResultTrial:
        - If the current trial is submitted, use it.
        - If the current trial is not submitted, use the previous trial (if it exists).
        """
        current_trial = self.current_trial
        if current_trial and current_trial.student_submitted_exam_at:
            return current_trial
        return self.previous_trial or current_trial

    @property
    def is_trials_finished(self):
        """Check if the student has finished his allowed trials."""
        # If all trials are submitted, check if we reached the limit
        if not self.trials.filter(student_submitted_exam_at__isnull=True).exists():
            return self.trial >= self.exam.number_of_allowed_trials
        # If there's an unsubmitted trial, trials are not finished
        return False

    @property
    def has_unsubmitted_trial(self):
        """Check if there's an unsubmitted trial."""
        return self.trials.filter(student_submitted_exam_at__isnull=True).exists()

    @property
    def is_succeeded(self):
        """Determine if the student passed the exam based on the active trial."""
        active_trial = self.active_trial
        if active_trial:
            return active_trial.score >= (self.exam.passing_percent / 100) * active_trial.exam_score
        return False

    @property
    def is_allowed_to_show_result(self):
        return timezone.now() >= self.exam.allow_show_results_at

    @property
    def is_allowed_to_show_answers(self):
        if self.exam.allow_show_answers_at:
            return timezone.now() >= self.exam.allow_show_answers_at
        return self.exam.show_answers_after_finish

    def get_best_trial_score(self):
        """
        Returns the highest score achieved across all trials for this result.
        Returns 0 if no trials exist.
        """
        best_trial = self.trials.order_by('-score').first()
        return best_trial.score if best_trial else 0.0
        
    def __str__(self):
        return f"{self.student.name} - {self.exam.title} | Trial: {self.trial}"


class ResultTrial(models.Model):
    # Define choices for the submit_type field
    SUBMIT_TYPE_CHOICES = [
        ('student_submit', 'Student Submit'),
        ('tab_closed', 'Tab Closed'),
        ('offline', 'Offline'),
        ('time_out', 'Time Out'),
    ]

    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name='trials')
    trial = models.PositiveIntegerField()
    score = models.FloatField(default=0.0)
    exam_score = models.FloatField(default=0.0)  
    exam_model = models.ForeignKey(ExamModel, on_delete=models.SET_NULL, null=True, blank=True)
    student_started_exam_at = models.DateTimeField()
    student_submitted_exam_at = models.DateTimeField(null=True, blank=True)

    submit_type = models.CharField(
        max_length=20,
        choices=SUBMIT_TYPE_CHOICES,
        default='student_submit',
        null=True,  
        blank=True,
    )

    class Meta:
        unique_together = ('result', 'trial')  # Ensure one trial per result
        indexes = [
            # For result-trial lookups
            models.Index(fields=['result', 'trial']),
            # For scoring and timing queries
            models.Index(fields=['score', 'exam_score']),
            # For submission time tracking
            models.Index(fields=['student_started_exam_at', 'student_submitted_exam_at']),
            # For filtering by submit type
            models.Index(fields=['submit_type', 'student_submitted_exam_at']),
        ]

    def __str__(self):
        return f"{self.id}"


class AddReasonChoices(models.TextChoices):
    INCORRECT = 'INCORRECT', _('Incorrect')
    UNSOLVED = 'UNSOLVED', _('Unsolved')
    PARTIAL_ESSAY = 'PARTIAL_ESSAY', _('Partial Essay Score')

class StudentBank(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='student_bank')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='student_bank')
    add_reason = models.CharField(max_length=20, choices=AddReasonChoices.choices)
    is_solved_now = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'question')
        indexes = [
            models.Index(fields=['student', 'question']),
            # Optimized for CreateTempExam filtering: StudentBank.objects.filter(student=student, is_solved_now=False, question__question_type='MCQ', question__is_active=True)
            models.Index(fields=['student', 'is_solved_now', 'question']),
            # For efficient question filtering in CreateTempExam
            models.Index(fields=['is_solved_now', 'question']),
            # For ID-range sampling optimization (Min/Max queries)
            models.Index(fields=['id', 'student', 'is_solved_now']),
        ]

    def __str__(self):
        return f"{self.student.name} - Q: {self.question.id} - {self.add_reason}"

class TempExam(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='temp_exams')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    number_of_questions = models.PositiveIntegerField()
    time_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Time limit in minutes")
    created = models.DateTimeField(auto_now_add=True)
    result = models.FloatField(null=True, blank=True)
    selected_questions_type = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        indexes = [
            # For student-based temp exam queries
            models.Index(fields=['student', 'created']),
            # For filtering by course/unit
            models.Index(fields=['course', 'unit']),
            # For date-based queries and limits
            models.Index(fields=['created', 'student']),
        ]

    def __str__(self):
        return f"Temp Exam for {self.student.name} - {self.created}"


class TempExamAllowedTimes(models.Model):
    number_of_allowedtempexams_per_day = models.PositiveIntegerField(default=3)

    class Meta:
        # Ensure only one instance exists
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name='single_instance_constraint'
            )
        ]

    def save(self, *args, **kwargs):
        self.id = 1  # Enforce single instance
        super().save(*args, **kwargs)
    def __str__(self):
        return f"Allowed Temp Exams: {self.number_of_allowedtempexams_per_day} per day"





#^ < ==============================[ <- Admin Question Bank -> ]============================== > ^#


class AdminQuestionBank(models.Model):
    """Model for admin to store questions for student-created exams"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='admin_question_bank')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # For efficient question lookups with creation time
            models.Index(fields=['created', 'question']),
            # For question-based filtering
            models.Index(fields=['question', 'created']),
        ]

    def __str__(self):
        return f"Admin Question Bank - Q: {self.question.id} - {self.created}"


#^ < ==============================[ <- Student Created Exams -> ]============================== > ^#


class StudentCreatedExam(models.Model):
    """Model for student-created exams using questions from admin question bank"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='created_exams')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    number_of_mcq_questions = models.PositiveIntegerField()
    number_of_essay_questions = models.PositiveIntegerField()
    time_limit = models.PositiveIntegerField(help_text="Time limit in minutes")
    created = models.DateTimeField(auto_now_add=True)
    exam_score = models.FloatField(default=0.0)
    result = models.FloatField(null=True, blank=True)
    
    class Meta:
        indexes = [
            # For student-based exam queries
            models.Index(fields=['student', 'created']),
            # For filtering by course/unit
            models.Index(fields=['course', 'unit']),
            # For date-based queries and limits
            models.Index(fields=['created', 'student']),
        ]

    def __str__(self):
        return f"Student Created Exam for {self.student.name} - {self.created}"
