from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import storages
from django.db import transaction
from django.db.models import Count, Max, Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from exam.models import StudentBank, TempExam, TempExamAllowedTimes, Answer, DifficultyLevel, EssaySubmission, Exam, ExamConfig, ExamModelQuestion, ExamQuestion, Question, QuestionCategory, QuestionImage, QuestionType, RandomExamBank, Result, ResultTrial, Submission, AdminQuestionBank, StudentCreatedExam, Year

# Register your models here.

class QuestionImageInline(admin.TabularInline):
    model = QuestionImage
    extra = 0
    fields = ('image', 'order')
    readonly_fields = ('created',)


class ExamChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, exam):
        owner = exam.student or 'legacy / no owner'
        return f'#{exam.pk} — {exam.title} — {owner}'


class AddAllQuestionsToExamForm(forms.Form):
    exam = ExamChoiceField(
        queryset=Exam.objects.select_related('student', 'student__user').order_by('-created', '-id'),
        label='Target exam',
    )


class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id','text', 'points', 'difficulty', 'category', 'course', 'unit', 'is_active', 'images_count', 'created')
    list_editable = ('is_active',)
    list_filter = ('difficulty', 'is_active', 'question_type', 'course', 'unit', 'category', 'years')
    filter_horizontal = ('similar_questions', 'years')
    search_fields = ('text', 'answers__text')
    inlines = (QuestionImageInline,)
    change_list_template = 'admin/exam/question/change_list.html'
    r2_audio_sync_batch_size = 25

    def has_add_all_questions_to_exam_permission(self, request):
        return request.user.is_active and request.user.is_staff and request.user.is_superuser

    def has_sync_local_audio_to_r2_permission(self, request):
        return request.user.is_active and request.user.is_staff and request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            'show_add_all_questions_to_exam': self.has_add_all_questions_to_exam_permission(request),
            'show_sync_local_audio_to_r2': self.has_sync_local_audio_to_r2_permission(request),
        }
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        custom_urls = [
            path(
                'add-all-to-exam/',
                self.admin_site.admin_view(self.add_all_questions_to_exam_view),
                name='exam_question_add_all_to_exam',
            ),
            path(
                'sync-local-explanation-audio-to-r2/',
                self.admin_site.admin_view(self.sync_local_audio_to_r2_view),
                name='exam_question_sync_local_audio_to_r2',
            ),
        ]
        return custom_urls + super().get_urls()

    @staticmethod
    def _local_question_audio_files():
        """Return safe local files and exact keys under question_explanations/audio/."""
        media_root = Path(settings.MEDIA_ROOT).resolve()
        audio_root = media_root / 'question_explanations' / 'audio'
        if not audio_root.is_dir():
            return media_root, []

        files = []
        for local_path in audio_root.rglob('*'):
            if local_path.is_symlink() or not local_path.is_file():
                continue
            try:
                resolved_path = local_path.resolve()
                resolved_path.relative_to(media_root)
            except (OSError, ValueError):
                continue
            files.append((resolved_path.relative_to(media_root).as_posix(), resolved_path))
        return media_root, sorted(files, key=lambda item: item[0])

    @staticmethod
    def _build_r2_audio_sync_storage():
        """Create an exact-key R2 storage without changing the global backend."""
        storage_config = dict(settings.STORAGES['default'])
        storage_options = dict(storage_config.get('OPTIONS', {}))
        storage_options['file_overwrite'] = True
        storage_config['OPTIONS'] = storage_options
        return storages.create_storage(storage_config)

    @staticmethod
    def _existing_r2_audio_keys(storage):
        """List audio keys once per batch instead of issuing one HEAD per file."""
        client = storage.connection.meta.client
        paginator = client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=storage.bucket_name,
            Prefix='question_explanations/audio/',
        )
        return {
            item['Key']
            for page in pages
            for item in page.get('Contents', [])
        }

    def sync_local_audio_to_r2_view(self, request):
        """Upload missing local question explanation audio to R2 in safe batches."""
        if not self.has_sync_local_audio_to_r2_permission(request):
            raise PermissionDenied

        media_root, local_files = self._local_question_audio_files()
        bucket_name = getattr(settings, 'R2_STORAGE_BUCKET_NAME', '')
        r2_is_active = (
            getattr(settings, 'MEDIA_STORAGE_BACKEND', None) == 'r2'
            and bool(bucket_name)
        )
        result = None

        if request.method == 'POST' and request.POST.get('confirm') == 'yes':
            if not r2_is_active or not bucket_name:
                self.message_user(
                    request,
                    'R2 is not active. Configure R2_STORAGE_BUCKET_NAME and restart Django first.',
                    level=messages.ERROR,
                )
            else:
                try:
                    storage = self._build_r2_audio_sync_storage()
                    existing_keys = self._existing_r2_audio_keys(storage)
                except Exception as exc:
                    self.message_user(
                        request,
                        f'Could not read the R2 bucket: {exc}',
                        level=messages.ERROR,
                    )
                else:
                    missing_files = [item for item in local_files if item[0] not in existing_keys]
                    current_batch = missing_files[:self.r2_audio_sync_batch_size]
                    uploaded_keys = []
                    failed_files = []

                    for storage_key, local_path in current_batch:
                        try:
                            with local_path.open('rb') as local_file:
                                saved_key = storage.save(
                                    storage_key,
                                    File(local_file, name=local_path.name),
                                )
                            if saved_key != storage_key:
                                raise RuntimeError(
                                    f'R2 returned unexpected object key {saved_key!r}'
                                )
                        except Exception as exc:
                            failed_files.append({
                                'key': storage_key,
                                'error': str(exc)[:300],
                            })
                        else:
                            uploaded_keys.append(storage_key)

                    remaining_count = len(missing_files) - len(uploaded_keys)
                    result = {
                        'already_in_r2': len(local_files) - len(missing_files),
                        'attempted': len(current_batch),
                        'uploaded': len(uploaded_keys),
                        'failed': failed_files,
                        'remaining': remaining_count,
                        'auto_continue': remaining_count > 0 and not failed_files,
                    }
                    if remaining_count == 0:
                        self.message_user(
                            request,
                            'All local question explanation audio files now exist in R2.',
                            level=messages.SUCCESS,
                        )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Sync local question explanation audio to R2',
            'opts': self.model._meta,
            'media_root': media_root,
            'local_count': len(local_files),
            'bucket_name': bucket_name,
            'r2_is_active': r2_is_active,
            'batch_size': self.r2_audio_sync_batch_size,
            'result': result,
            'question_changelist_url': reverse('admin:exam_question_changelist'),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            'admin/exam/question/sync_local_audio_to_r2.html',
            context,
        )

    @staticmethod
    def _add_all_questions_preview(exam):
        question_stats = Question.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            mcq=Count('id', filter=Q(question_type=QuestionType.MCQ)),
            essay=Count('id', filter=Q(question_type=QuestionType.ESSAY)),
        )
        linked_question_count = (
            ExamQuestion.objects
            .filter(exam=exam)
            .values('question_id')
            .distinct()
            .count()
        )
        return {
            'exam': exam,
            **question_stats,
            'inactive': question_stats['total'] - question_stats['active'],
            'already_linked': linked_question_count,
            'to_add': max(question_stats['total'] - linked_question_count, 0),
            'inactive_links_to_reactivate': ExamQuestion.objects.filter(
                exam=exam,
                is_active=False,
            ).count(),
            'existing_trials': ResultTrial.objects.filter(result__exam=exam).count(),
        }

    @staticmethod
    @transaction.atomic
    def _attach_all_questions(exam_id):
        exam = Exam.objects.select_for_update().get(pk=exam_id)
        question_ids = list(
            Question.objects.order_by('id').values_list('id', flat=True)
        )
        relations = ExamQuestion.objects.filter(exam=exam)
        existing_question_ids = set(relations.values_list('question_id', flat=True))
        reactivated_count = relations.filter(is_active=False).update(is_active=True)
        next_order = (relations.aggregate(max_order=Max('order'))['max_order'] or 0) + 1
        missing_question_ids = [
            question_id
            for question_id in question_ids
            if question_id not in existing_question_ids
        ]
        ExamQuestion.objects.bulk_create(
            [
                ExamQuestion(
                    exam=exam,
                    question_id=question_id,
                    is_active=True,
                    order=next_order + offset,
                )
                for offset, question_id in enumerate(missing_question_ids)
            ],
            batch_size=1000,
        )

        active_relations = ExamQuestion.objects.filter(exam=exam, is_active=True)
        counters = active_relations.aggregate(
            total=Count('id'),
            easy=Count('id', filter=Q(question__difficulty=DifficultyLevel.EASY)),
            medium=Count('id', filter=Q(question__difficulty=DifficultyLevel.MEDIUM)),
            hard=Count('id', filter=Q(question__difficulty=DifficultyLevel.HARD)),
        )
        Exam.objects.filter(pk=exam.pk).update(
            number_of_questions=counters['total'],
            easy_questions_count=counters['easy'],
            medium_questions_count=counters['medium'],
            hard_questions_count=counters['hard'],
        )
        return {
            'exam': exam,
            'added': len(missing_question_ids),
            'reactivated': reactivated_count,
            'total': counters['total'],
        }

    def add_all_questions_to_exam_view(self, request):
        if not self.has_add_all_questions_to_exam_permission(request):
            raise PermissionDenied

        form = AddAllQuestionsToExamForm(request.POST or None)
        preview = None
        if request.method == 'POST' and form.is_valid():
            exam = form.cleaned_data['exam']
            if request.POST.get('confirm') == 'yes':
                result = self._attach_all_questions(exam.pk)
                self.message_user(
                    request,
                    (
                        f"Added {result['added']} question link(s), reactivated "
                        f"{result['reactivated']}, and set exam #{exam.pk} to "
                        f"{result['total']} active question relation(s)."
                    ),
                    level=messages.SUCCESS,
                )
                return redirect('admin:exam_question_changelist')
            preview = self._add_all_questions_preview(exam)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Add all questions to an exam',
            'opts': self.model._meta,
            'form': form,
            'preview': preview,
            'question_changelist_url': reverse('admin:exam_question_changelist'),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            'admin/exam/question/add_all_questions_to_exam.html',
            context,
        )

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
    change_list_template = 'admin/exam/questionimage/change_list.html'
    r2_sync_batch_size = 25

    def has_sync_local_images_to_r2_permission(self, request):
        return request.user.is_active and request.user.is_staff and request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        extra_context = {
            **(extra_context or {}),
            'show_sync_local_images_to_r2': self.has_sync_local_images_to_r2_permission(request),
        }
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        custom_urls = [
            path(
                'sync-local-images-to-r2/',
                self.admin_site.admin_view(self.sync_local_images_to_r2_view),
                name='exam_questionimage_sync_local_images_to_r2',
            ),
        ]
        return custom_urls + super().get_urls()

    @staticmethod
    def _local_question_image_files():
        """Return safe local files and their storage keys under questions/."""
        media_root = Path(settings.MEDIA_ROOT).resolve()
        questions_root = media_root / 'questions'
        if not questions_root.is_dir():
            return media_root, []

        files = []
        for local_path in questions_root.rglob('*'):
            if local_path.is_symlink() or not local_path.is_file():
                continue
            try:
                resolved_path = local_path.resolve()
                resolved_path.relative_to(media_root)
            except (OSError, ValueError):
                continue
            files.append((resolved_path.relative_to(media_root).as_posix(), resolved_path))
        return media_root, sorted(files, key=lambda item: item[0])

    @staticmethod
    def _build_r2_sync_storage():
        """Create an exact-key R2 storage without changing the global backend."""
        storage_config = dict(settings.STORAGES['default'])
        storage_options = dict(storage_config.get('OPTIONS', {}))
        storage_options['file_overwrite'] = True
        storage_config['OPTIONS'] = storage_options
        return storages.create_storage(storage_config)

    @staticmethod
    def _existing_r2_question_keys(storage):
        """List R2 keys once per batch instead of issuing one HEAD per file."""
        client = storage.connection.meta.client
        paginator = client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=storage.bucket_name,
            Prefix='questions/',
        )
        return {
            item['Key']
            for page in pages
            for item in page.get('Contents', [])
        }

    def sync_local_images_to_r2_view(self, request):
        """Upload missing MEDIA_ROOT/questions files to R2 in safe batches."""
        if not self.has_sync_local_images_to_r2_permission(request):
            raise PermissionDenied

        media_root, local_files = self._local_question_image_files()
        bucket_name = getattr(settings, 'R2_STORAGE_BUCKET_NAME', '')
        r2_is_active = (
            getattr(settings, 'MEDIA_STORAGE_BACKEND', None) == 'r2'
            and bool(bucket_name)
        )
        result = None

        if request.method == 'POST' and request.POST.get('confirm') == 'yes':
            if not r2_is_active or not bucket_name:
                self.message_user(
                    request,
                    'R2 is not active. Configure R2_STORAGE_BUCKET_NAME and restart Django first.',
                    level=messages.ERROR,
                )
            else:
                try:
                    storage = self._build_r2_sync_storage()
                    existing_keys = self._existing_r2_question_keys(storage)
                except Exception as exc:
                    self.message_user(
                        request,
                        f'Could not read the R2 bucket: {exc}',
                        level=messages.ERROR,
                    )
                else:
                    missing_files = [item for item in local_files if item[0] not in existing_keys]
                    current_batch = missing_files[:self.r2_sync_batch_size]
                    uploaded_keys = []
                    failed_files = []

                    for storage_key, local_path in current_batch:
                        try:
                            with local_path.open('rb') as local_file:
                                saved_key = storage.save(
                                    storage_key,
                                    File(local_file, name=local_path.name),
                                )
                            if saved_key != storage_key:
                                raise RuntimeError(
                                    f'R2 returned unexpected object key {saved_key!r}'
                                )
                        except Exception as exc:
                            failed_files.append({
                                'key': storage_key,
                                'error': str(exc)[:300],
                            })
                        else:
                            uploaded_keys.append(storage_key)

                    remaining_count = len(missing_files) - len(uploaded_keys)
                    result = {
                        'already_in_r2': len(local_files) - len(missing_files),
                        'attempted': len(current_batch),
                        'uploaded': len(uploaded_keys),
                        'failed': failed_files,
                        'remaining': remaining_count,
                        'auto_continue': remaining_count > 0 and not failed_files,
                    }
                    if remaining_count == 0:
                        self.message_user(
                            request,
                            'All local question images now exist in R2.',
                            level=messages.SUCCESS,
                        )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Sync local question images to R2',
            'opts': self.model._meta,
            'media_root': media_root,
            'local_count': len(local_files),
            'bucket_name': bucket_name,
            'r2_is_active': r2_is_active,
            'batch_size': self.r2_sync_batch_size,
            'result': result,
            'question_image_changelist_url': reverse('admin:exam_questionimage_changelist'),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            'admin/exam/questionimage/sync_local_images_to_r2.html',
            context,
        )


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'student',
        'course',
        'unit',
        'category',
        'number_of_questions',
        'time_limit',
        'created',
    )
    list_filter = ('course', 'unit', 'category', 'years')
    search_fields = ('title', 'student__name', 'student__user__username', 'course__name', 'unit__name')
    filter_horizontal = ('years',)
    readonly_fields = [field.name for field in Exam._meta.fields] + ['years']
    actions = ('detach_questions_from_selected_legacy_exams',)

    def has_detach_questions_permission(self, request):
        """Limit the destructive cleanup action to superusers."""
        return request.user.is_active and request.user.is_staff and request.user.is_superuser

    @staticmethod
    def _question_relation_counts(exam_ids):
        random_bank_ids = RandomExamBank.objects.filter(
            exam_id__in=exam_ids
        ).values_list('id', flat=True)
        direct_count = ExamQuestion.objects.filter(exam_id__in=exam_ids).count()
        random_bank_count = RandomExamBank.questions.through.objects.filter(
            randomexambank_id__in=random_bank_ids
        ).count()
        exam_model_count = ExamModelQuestion.objects.filter(
            exam_model__exam_id__in=exam_ids
        ).count()
        return {
            'direct': direct_count,
            'random_bank': random_bank_count,
            'exam_model': exam_model_count,
            'total': direct_count + random_bank_count + exam_model_count,
        }

    @admin.action(
        permissions=('detach_questions',),
        description='Detach questions from selected legacy exams (preserve questions)',
    )
    def detach_questions_from_selected_legacy_exams(self, request, queryset):
        """Remove exam composition links without deleting Question-owned data."""
        exam_ids = list(queryset.values_list('id', flat=True))
        if not exam_ids:
            self.message_user(request, 'No exams were selected.', level=messages.WARNING)
            return None

        student_owned_count = queryset.exclude(student__isnull=True).count()
        if student_owned_count:
            self.message_user(
                request,
                (
                    'Nothing was detached. The selection contains '
                    f'{student_owned_count} student-owned exam(s); only legacy exams '
                    'with no owner can use this action.'
                ),
                level=messages.ERROR,
            )
            return None

        counts = self._question_relation_counts(exam_ids)
        if request.POST.get('confirm') != 'yes':
            context = {
                **self.admin_site.each_context(request),
                'title': 'Confirm detaching questions from legacy exams',
                'opts': self.model._meta,
                'action_checkbox_name': ACTION_CHECKBOX_NAME,
                'selected_ids': request.POST.getlist(ACTION_CHECKBOX_NAME),
                'select_across': request.POST.get('select_across', '0'),
                'exam_count': len(exam_ids),
                'relation_counts': counts,
            }
            return TemplateResponse(
                request,
                'admin/exam/exam/detach_questions_confirmation.html',
                context,
            )

        random_bank_ids = list(
            RandomExamBank.objects.filter(exam_id__in=exam_ids).values_list('id', flat=True)
        )
        with transaction.atomic():
            ExamQuestion.objects.filter(exam_id__in=exam_ids).delete()
            RandomExamBank.questions.through.objects.filter(
                randomexambank_id__in=random_bank_ids
            ).delete()
            ExamModelQuestion.objects.filter(
                exam_model__exam_id__in=exam_ids
            ).delete()
            Exam.objects.filter(id__in=exam_ids).update(
                number_of_questions=0,
                easy_questions_count=0,
                medium_questions_count=0,
                hard_questions_count=0,
            )

        self.message_user(
            request,
            (
                f"Detached {counts['total']} question relationship(s) from "
                f'{len(exam_ids)} legacy exam(s). Question records and their '
                'answers, images, and years were preserved.'
            ),
            level=messages.SUCCESS,
        )
        return None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExamConfig)
class ExamConfigAdmin(admin.ModelAdmin):
    list_display = ('max_trials_per_day', 'max_trials_per_week', 'max_trials_per_month')

    def has_add_permission(self, request):
        return not ExamConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


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
    list_filter = ('exam', 'is_active', 'order')
    search_fields = ('exam__title', 'question__text')
    readonly_fields = ('exam', 'question', 'is_active', 'order', 'created', 'updated')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
