from django.contrib import admin
from django.db.models import Max

from exam.models import StudentBank, TempExam, TempExamAllowedTimes, Answer, EssaySubmission, Exam, ExamQuestion, Question, QuestionCategory, QuestionImage, Result, ResultTrial, Submission, AdminQuestionBank, StudentCreatedExam, Year

# Register your models here.

class QuestionImageInline(admin.TabularInline):
    model = QuestionImage
    extra = 0
    fields = ('image', 'order')
    readonly_fields = ('created',)


class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id','text', 'points', 'difficulty', 'category', 'course', 'unit', 'is_active', 'images_count', 'created')
    list_editable = ('is_active',)
    list_filter = ('difficulty', 'is_active', 'question_type', 'course', 'unit', 'category', 'years')
    filter_horizontal = ('similar_questions', 'years')
    search_fields = ('text', 'answers__text')
    inlines = (QuestionImageInline,)

    @admin.display(description='Images')
    def images_count(self, obj):
        return obj.images.count()

admin.site.register(QuestionCategory)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Answer)


@admin.register(QuestionImage)
class QuestionImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'image', 'order', 'created')
    list_filter = ('question__course', 'question__unit')
    search_fields = ('question__text', 'image')
    ordering = ('question', 'order', 'id')


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'course',
        'unit',
        'is_active',
        'allow_unsubscribed_access',
        'start',
        'end',
    )
    list_editable = ('is_active', 'allow_unsubscribed_access')
    list_filter = ('allow_unsubscribed_access', 'is_active', 'related_to', 'type', 'course', 'unit')
    search_fields = ('title', 'description', 'course__name', 'unit__name')


@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    list_display = ("id", "value")
    search_fields = ("value",)
    ordering = ("-value",)
# admin.site.register(Submission)
# admin.site.register(EssaySubmission)
# admin.site.register(Result)
# admin.site.register(ResultTrial)
# admin.site.register(ExamQuestion)

@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ('exam', 'question', 'is_active', 'order', 'created')
    list_editable = ('is_active', 'order')
    list_filter = ('exam', 'is_active', 'order')
    search_fields = ('exam__title', 'question__text')


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Submission model.
    Allows for easy viewing and filtering of student submissions.
    """
    list_display = (
        'id', # Always good to have the ID
        'student',
        'exam',
        'question',
        'selected_answer',
        'is_correct',
        'is_solved',
        'result_trial',
    )
    list_filter = (
        'exam', # Filter by the associated exam
        'student', # Filter by the submitting student
        'is_correct', # Filter by whether the answer was correct
        'is_solved', # Filter by whether the question was solved
        'result_trial', # Filter by the associated result trial
    )
    search_fields = (
        'student__user__username', # Assuming Student model has a user field with username
        'student__full_name', # If Student has a full_name field
        'exam__title', # Search by exam title
        'question__text', # Search by question text
    )
    raw_id_fields = ('student', 'exam', 'question', 'selected_answer', 'result_trial') # Use raw_id_fields for FKs to improve performance for many records

@admin.register(EssaySubmission)
class EssaySubmissionAdmin(admin.ModelAdmin):
    """
    Admin configuration for the EssaySubmission model.
    Provides tools for managing and scoring essay type submissions.
    """
    list_display = (
        'id', # Always good to have the ID
        'student',
        'exam',
        'question',
        'score',
        'is_scored',
        'created',
        'result_trial',
        'answer_file', # Display if a file was uploaded
    )
    list_filter = (
        'exam', # Filter by the associated exam
        'student', # Filter by the submitting student
        'is_scored', # Filter by whether the essay has been scored
        'result_trial', # Filter by the associated result trial
        'created', # Filter by creation date
    )
    search_fields = (
        'student__user__username', # Assuming Student model has a user field with username
        'student__full_name', # If Student has a full_name field
        'exam__title', # Search by exam title
        'question__text', # Search by question text
        'answer_text', # Search within the essay answer text
    )
    raw_id_fields = ('student', 'exam', 'question', 'result_trial') # Use raw_id_fields for FKs
    readonly_fields = ('created',) # Make 'created' field read-only in the admin

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Result model.
    Manages overall exam results for students.
    """
    list_display = (
        'id',
        'student',
        'exam',
        'trial',
        'added',
        'exam_model',
        'is_succeeded',         # Property from the Result model
        'is_trials_finished',   # Property from the Result model
        'has_unsubmitted_trial',# Property from the Result model
        'has_unsubscribed_submission',
    )
    list_filter = (
        'exam',
        'student',
        'trial',
        'exam_model',
        'added', # Filter by date added
        'trials__submitted_by_unsubscribed_user',
    )
    search_fields = (
        'student__user__username',
        'student__full_name',
        'exam__title',
    )
    raw_id_fields = ('student', 'exam', 'exam_model')
    readonly_fields = ('added',) # 'added' is auto_now_add, so it should be read-only


@admin.register(ResultTrial)
class ResultTrialAdmin(admin.ModelAdmin):
    """
    Admin configuration for the ResultTrial model.
    Manages individual trial attempts within a student's exam result.
    """
    list_display = (
        'id',
        'result',
        'trial',
        'score',
        'exam_score',
        'exam_model',
        'student_started_exam_at',
        'student_submitted_exam_at',
        'submit_type',
        'submitted_by_unsubscribed_user',
    )
    list_filter = (
        'result__exam', # Filter by the exam associated with the parent result
        'result__student', # Filter by the student associated with the parent result
        'trial',
        'submit_type',
        'submitted_by_unsubscribed_user',
        'exam_model',
        'student_started_exam_at', # Filter by start date
        'student_submitted_exam_at', # Filter by submission date
    )
    search_fields = (
        'result__student__user__username',
        'result__student__full_name',
        'result__exam__title',
    )
    raw_id_fields = ('result', 'exam_model')



@admin.register(StudentBank)
class StudentBankAdmin(admin.ModelAdmin):
    """
    Admin configuration for the StudentBank model.
    """
    # Fields to display in the change list view
    list_display = ('student', 'question_id', 'add_reason', 'is_solved_now', 'created')

    # Fields to use for filtering in the right sidebar
    list_filter = ('add_reason', 'is_solved_now', 'created')

    # Fields to enable searching on
    search_fields = ('student__name', 'student__user__username', 'question__id')
    
    # Help text for search
    search_help_text = "Search by Student Name, Username, or Question ID."

    # Use a raw_id_widget for foreign key fields to improve performance
    # This is especially useful for large numbers of students or questions
    raw_id_fields = ('student', 'question')

    # Number of items to display per page
    list_per_page = 25

    # Make created field read-only as it's set automatically
    readonly_fields = ('created',)

    # Customize the fieldsets for a better layout in the add/change form
    fieldsets = (
        (None, {
            'fields': ('student', 'question')
        }),
        ('Status Details', {
            'fields': ('add_reason', 'is_solved_now')
        }),
        ('Timestamps', {
            'fields': ('created',)
        }),
    )

    def question_id(self, obj):
        """A method to display the question's ID for clarity."""
        return obj.question.id
    question_id.short_description = 'Question ID'
    question_id.admin_order_field = 'question'


@admin.register(TempExam)
class TempExamAdmin(admin.ModelAdmin):
    """
    Admin configuration for the TempExam model.
    """
    # Fields to display in the change list view
    list_display = ('student', 'result', 'number_of_questions', 'time_limit', 'selected_questions_type', 'created')

    # Fields for filtering
    list_filter = ('course', 'unit', 'selected_questions_type', 'created')

    # Fields for searching
    search_fields = ('student__name', 'student__user__username')
    search_help_text = "Search by Student Name or Username."

    # Read-only fields in the admin form
    readonly_fields = ('created', 'result')

    # Use raw_id_fields for better performance with foreign keys
    raw_id_fields = ('student', 'course', 'unit')

    # Number of items per page
    list_per_page = 20

    # Fieldsets for a structured add/change form
    fieldsets = (
        ('Exam Setup', {
            'fields': ('student', ('number_of_questions', 'time_limit'), 'selected_questions_type')
        }),
        ('Content Source (Optional)', {
            'classes': ('collapse',), # Make this section collapsible
            'fields': ('course', 'unit'),
        }),
        ('Exam Outcome', {
            'fields': ('result', 'created')
        }),
    )

@admin.register(TempExamAllowedTimes)
class TempExamAllowedTimesAdmin(admin.ModelAdmin):
    """
    Admin configuration for the TempExamAllowedTimes singleton model.
    This ensures that only one instance of this configuration can exist.
    """
    list_display = ('number_of_allowedtempexams_per_day',)

    def has_add_permission(self, request):
        """
        Prevent adding new instances if one already exists.
        The model logic already enforces a single instance with id=1.
        """
        return not TempExamAllowedTimes.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """
        Prevent deleting the settings object.
        """
        return False 


#^ ------- Student Created Exams Admin ------- ^#

@admin.register(AdminQuestionBank)
class AdminQuestionBankAdmin(admin.ModelAdmin):
    """
    Admin configuration for the AdminQuestionBank model.
    Allows admins to manage questions available for student-created exams.
    """
    list_display = (
        'id',
        'question',
        'get_question_text',
        'get_question_type',
        'get_question_points',
        'created'
    )
    list_filter = (
        'question__question_type',
        'question__course',
        'question__unit',
        'question__difficulty',
        'created'
    )
    search_fields = ('question__text', 'question__course__name', 'question__unit__name')
    readonly_fields = ('created',)
    
    def get_question_text(self, obj):
        return obj.question.text[:50] + "..." if len(obj.question.text) > 50 else obj.question.text
    get_question_text.short_description = 'Question Text'
    
    def get_question_type(self, obj):
        return obj.question.question_type
    get_question_type.short_description = 'Type'
    
    def get_question_points(self, obj):
        return obj.question.points
    get_question_points.short_description = 'Points'


@admin.register(StudentCreatedExam)
class StudentCreatedExamAdmin(admin.ModelAdmin):
    """
    Admin configuration for the StudentCreatedExam model.
    """
    list_display = (
        'id',
        'student',
        'course',
        'unit',
        'number_of_mcq_questions',
        'number_of_essay_questions',
        'get_total_questions',
        'time_limit',
        'exam_score',
        'result',
        'get_percentage',
        'created'
    )
    list_filter = (
        'course',
        'unit',
        'created',
        'student'
    )
    search_fields = ('student__name', 'course__name', 'unit__name')
    readonly_fields = ('created', 'exam_score')
    
    def get_total_questions(self, obj):
        return obj.number_of_mcq_questions + obj.number_of_essay_questions
    get_total_questions.short_description = 'Total Questions'
    
    def get_percentage(self, obj):
        if obj.result is not None and obj.exam_score > 0:
            return f"{(obj.result / obj.exam_score * 100):.1f}%"
        return "Not submitted"
    get_percentage.short_description = 'Percentage'
