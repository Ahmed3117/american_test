import json

from django.contrib import admin
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .models import DiscountCoupon, EasyPayWebhookEvent, Plan, PlanSubscription, PlanSubscriptionCourse


def admin_link(model, pk, label):
    url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_change', args=[pk])
    return format_html('<a href="{}">{}</a>', url, label)


def pretty_summary(payload):
    # Historical subscription payloads can contain signatures and arbitrary
    # provider data. Show only known diagnostic fields, never raw JSON/HTML.
    allowed = ('amount', 'payment_amount', 'customer_phone', 'phone', 'status', 'payment_status',
               'easy_pay_sequence', 'invoice_sequence', 'invoiceSequence', 'invoice_uid', 'invoiceUid')
    safe = {
        key: (str(payload[key])[:255] if isinstance(payload[key], (str, int, float)) else '[non-scalar value omitted]')
        for key in allowed if isinstance(payload, dict) and key in payload
    }
    return format_html('<pre style="white-space:pre-wrap;overflow-wrap:anywhere">{}</pre>',
                       json.dumps(safe, indent=2, ensure_ascii=False))


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'price', 'is_active', 'start_date', 'end_date', 'number_of_allowed_courses_to_subscribe')
    list_filter = ('is_active',)
    search_fields = ('title',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DiscountCoupon)
class DiscountCouponAdmin(admin.ModelAdmin):
    list_display = ('id', 'coupon', 'plan', 'discount_percentage', 'is_active', 'valid_from', 'valid_to', 'max_using_number')
    list_filter = ('is_active', 'plan', 'valid_from', 'valid_to')
    search_fields = ('coupon', 'plan__title')
    list_select_related = ('plan',)
    readonly_fields = ('coupon', 'created_at', 'updated_at')


class SubscriptionAccessFilter(admin.SimpleListFilter):
    title = 'Access window (stored dates)'
    parameter_name = 'access_window'

    def lookups(self, request, model_admin):
        return [('active', 'Accessible now'), ('expired', 'Paid, expired'), ('future', 'Paid, not started'),
                ('inactive', 'Inactive plan'), ('unpaid', 'Not paid'), ('legacy', 'Missing stored dates')]

    def queryset(self, request, queryset):
        today = timezone.localdate()
        paid = Q(payment_status__in=['paid', 'manual'])
        complete = Q(access_starts_on__isnull=False, access_ends_on__isnull=False)
        choices = {
            'active': paid & complete & Q(plan__is_active=True, access_starts_on__lte=today, access_ends_on__gte=today),
            'expired': paid & complete & Q(access_ends_on__lt=today),
            'future': paid & complete & Q(access_starts_on__gt=today),
            'inactive': Q(plan__is_active=False), 'unpaid': ~paid, 'legacy': ~complete,
        }
        return queryset.filter(choices[self.value()]) if self.value() in choices else queryset


class SubscriptionDiagnosticFilter(admin.SimpleListFilter):
    title = 'Needs investigation'
    parameter_name = 'diagnostic'

    def lookups(self, request, model_admin):
        return [('missing_sequence', 'Missing invoice sequence'), ('duplicate_sequence', 'Duplicate invoice sequence'),
                ('paid_no_sequence', 'Paid without sequence (not manual)'), ('paid_no_date', 'Paid without paid-at'),
                ('paid_no_verified_delivery', 'Paid without verified delivery history'),
                ('no_courses', 'No selected courses'), ('delivery_error', 'Latest linked delivery failed')]

    def queryset(self, request, queryset):
        missing_sequence = Q(easypay_invoice_sequence__isnull=True) | Q(easypay_invoice_sequence='')
        choices = {
            'missing_sequence': missing_sequence, 'duplicate_sequence': Q(duplicate_sequence=True),
            'paid_no_sequence': Q(payment_status='paid') & missing_sequence,
            'paid_no_date': Q(payment_status__in=['paid', 'manual'], paid_at__isnull=True),
            'paid_no_verified_delivery': Q(payment_status='paid', verified_delivery=False),
            'no_courses': Q(selected_course_count=0),
            'delivery_error': Q(last_delivery_outcome__in=['rejected', 'unmatched', 'ambiguous', 'config_error', 'error']),
        }
        return queryset.filter(choices[self.value()]) if self.value() in choices else queryset


@admin.register(PlanSubscription)
class PlanSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'student_identity', 'plan', 'payment_status', 'access_now', 'invoice_total',
                    'easypay_invoice_sequence', 'course_count', 'delivery_count', 'last_delivery_at', 'diagnostics', 'paid_at', 'created_at')
    list_filter = ('payment_status', SubscriptionAccessFilter, SubscriptionDiagnosticFilter,
                   'plan', 'courses', 'student__user__academic_year', 'paid_at', 'created_at', 'access_starts_on', 'access_ends_on')
    search_fields = ('student__name', 'student__user__name', 'student__user__username', 'student__code',
                     'plan__title', 'easypay_invoice_sequence', 'easypay_invoice_uid', 'discount_coupon__coupon')
    search_help_text = 'Student name / phone / code, plan, coupon, invoice UID or sequence; numeric subscription, User or Student ID.'
    ordering = ('-created_at', '-id')
    date_hierarchy = 'created_at'
    list_per_page = 50
    show_full_result_count = False
    raw_id_fields = ('student', 'plan', 'discount_coupon')
    exclude = ('easypay_payload',)
    fieldsets = (
        ('Investigation summary', {'fields': ('id', 'student_identity', 'access_now', 'diagnostics', 'delivery_history')}),
        ('Student and purchase', {'fields': ('student', 'plan', 'selected_courses', 'payment_status')}),
        ('Price and discount', {'fields': ('invoice_total', 'original_price', 'discount_coupon', 'discount_amount', 'payable_amount', 'coupon_applied_at')}),
        ('Course access window', {'fields': ('access_starts_on', 'access_ends_on', 'effective_window'),
                                 'description': 'Payment does not extend these dates. Inactive/expired plans do not grant access. Missing dates use the existing legacy plan-period fallback.'}),
        ('EasyPay invoice', {'fields': ('easypay_invoice_uid', 'easypay_invoice_sequence', 'easypay_payment_url'),
                            'description': 'Missing or duplicate sequences need manual provider reconciliation; this page does not verify payment with EasyPay.'}),
        ('Last saved provider payload (safe summary)', {'fields': ('payload_summary',), 'classes': ('collapse',),
                                                     'description': 'Not a delivery history and not proof of a verified payment. Signatures and unknown fields are hidden.'}),
        ('Timestamps', {'fields': ('paid_at', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('id', 'student_identity', 'access_now', 'diagnostics', 'delivery_history', 'selected_courses',
                       'invoice_total', 'effective_window', 'payload_summary', 'created_at', 'updated_at', 'paid_at')

    def get_queryset(self, request):
        duplicate = PlanSubscription.objects.filter(easypay_invoice_sequence=OuterRef('easypay_invoice_sequence')).exclude(
            pk=OuterRef('pk')).exclude(easypay_invoice_sequence='')
        latest = EasyPayWebhookEvent.objects.filter(subscription_id=OuterRef('pk')).order_by('-received_at', '-id')
        return super().get_queryset(request).select_related('student__user', 'plan', 'discount_coupon').prefetch_related('courses').annotate(
            selected_course_count=Count('courses', distinct=True), deliveries_count=Count('webhook_events', distinct=True),
            duplicate_sequence=Exists(duplicate), last_delivery_outcome=Subquery(latest.values('outcome')[:1]),
            last_delivery_at=Subquery(latest.values('received_at')[:1]),
            verified_delivery=Exists(EasyPayWebhookEvent.objects.filter(
                subscription_id=OuterRef('pk'), outcome__in=['paid', 'already_paid'], signature_valid=True)),
        )

    def get_search_results(self, request, queryset, search_term):
        result, duplicates = super().get_search_results(request, queryset, search_term)
        if search_term.isdecimal() and len(search_term) <= 19 and int(search_term) <= 9223372036854775807:
            result = result | queryset.filter(Q(pk=search_term) | Q(student_id=search_term) | Q(student__user_id=search_term))
        return result, duplicates

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_paid:
            return tuple(dict.fromkeys((*self.readonly_fields, *(field.name for field in obj._meta.fields))))
        return self.readonly_fields

    @admin.display(description='Student / phone / IDs')
    def student_identity(self, obj):
        if not obj or not obj.student_id:
            return '—'
        return admin_link(obj.student.user.__class__, obj.student.user_id,
                          f'{obj.student.name} | {obj.student.user.username} | User {obj.student.user_id} / Student {obj.student_id}')

    @admin.display(boolean=True, description='Access now')
    def access_now(self, obj):
        return obj.has_access_now if obj and obj.pk else None

    @admin.display(description='Invoice amount')
    def invoice_total(self, obj):
        return obj.invoice_amount if obj and obj.plan_id else '—'

    @admin.display(description='Selected courses', ordering='selected_course_count')
    def course_count(self, obj):
        return obj.selected_course_count

    @admin.display(description='Last webhook received', ordering='last_delivery_at')
    def last_delivery_at(self, obj):
        return obj.last_delivery_at

    @admin.display(description='Webhook deliveries', ordering='deliveries_count')
    def delivery_count(self, obj):
        url = reverse('admin:subscription_easypaywebhookevent_changelist') + f'?subscription__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, obj.deliveries_count)

    @admin.display(description='Selected courses (read-only)')
    def selected_courses(self, obj):
        return ', '.join(course.name for course in obj.courses.all()) if obj and obj.pk else '—'

    @admin.display(description='Effective access dates')
    def effective_window(self, obj):
        if not obj or not obj.plan_id:
            return '—'
        start, end = obj.access_period
        return f'{start} → {end}'

    @admin.display(description='Warnings / checks')
    def diagnostics(self, obj):
        if not obj or not obj.pk:
            return 'Save the subscription to see diagnostics.'
        warnings = []
        if obj.payment_status == 'paid' and not obj.easypay_invoice_sequence:
            warnings.append('PAID without invoice sequence — reconcile with EasyPay.')
        if getattr(obj, 'duplicate_sequence', False):
            warnings.append('Duplicate invoice sequence — callbacks cannot be matched safely.')
        if obj.is_paid and not obj.paid_at:
            warnings.append('Paid status without a paid-at timestamp.')
        if obj.payment_status == 'paid' and not getattr(obj, 'verified_delivery', False):
            warnings.append('No verified payment delivery recorded — may predate tracking; reconcile if needed.')
        if obj.is_paid and not obj.has_access_now:
            warnings.append('Paid but no current access — check plan activation and dates.')
        if getattr(obj, 'selected_course_count', None) == 0:
            warnings.append('No courses selected — no course access is granted.')
        if not obj.access_starts_on or not obj.access_ends_on:
            warnings.append('Missing stored dates — legacy period fallback is in use.')
        payload = obj.easypay_payload if isinstance(obj.easypay_payload, dict) else {}
        sequence = payload.get('easy_pay_sequence') or payload.get('invoice_sequence') or payload.get('invoiceSequence')
        if sequence and str(sequence) != (obj.easypay_invoice_sequence or ''):
            warnings.append('Last saved payload sequence differs from the saved invoice sequence.')
        if getattr(obj, 'last_delivery_outcome', None) in ('rejected', 'ambiguous', 'error', 'config_error'):
            warnings.append('Latest linked webhook delivery failed — open delivery history.')
        if not warnings:
            return 'No listed warning detected (not an independent payment verification).'
        return format_html_join('', '<div style="color:var(--error-fg,#ba2121)">⚠ {}</div>', ((item,) for item in warnings))

    @admin.display(description='Last saved payload (redacted)')
    def payload_summary(self, obj):
        return pretty_summary(obj.easypay_payload if obj else {})

    @admin.display(description='Recent webhook deliveries')
    def delivery_history(self, obj):
        if not obj or not obj.pk:
            return '—'
        rows = obj.webhook_events.order_by('-received_at', '-id')[:10]
        url = reverse('admin:subscription_easypaywebhookevent_changelist') + f'?subscription__id__exact={obj.pk}'
        return format_html('<a href="{}">All linked deliveries</a><br>{}', url,
                           format_html_join('<br>', '{} | {} | HTTP {} | {}',
                                            ((event.received_at, event.get_outcome_display(), event.http_status, event.reason) for event in rows)))


@admin.register(EasyPayWebhookEvent)
class EasyPayWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'received_at', 'outcome', 'http_status', 'sequence', 'subscription_link',
                    'customer_phone', 'amount', 'provider_status', 'signature_valid', 'reason')
    list_filter = ('outcome', 'http_status', 'signature_valid', 'signature_present', 'subscription__plan', 'received_at')
    search_fields = ('sequence', 'invoice_uid', 'customer_phone', 'subscription__student__name',
                     'subscription__student__user__username', 'subscription__plan__title', 'reason')
    date_hierarchy = 'received_at'
    list_per_page = 50
    show_full_result_count = False
    list_select_related = ('subscription__student__user', 'subscription__plan')
    readonly_fields = tuple(field.name for field in EasyPayWebhookEvent._meta.fields) + ('safe_request', 'subscription_link')
    fieldsets = (
        ('Delivery outcome', {'fields': ('id', 'received_at', 'outcome', 'http_status', 'reason', 'subscription_link')}),
        ('Provider invoice and customer', {'fields': ('sequence', 'invoice_uid', 'customer_phone', 'amount', 'provider_status')}),
        ('Authentication checks', {'fields': ('signature_present', 'signature_valid'),
                                   'description': 'Unknown means verification was not reached. A valid signature alone does not prove amount/phone matching or payment activation.'}),
        ('Safe request summary', {'fields': ('safe_request',)}),
    )

    @admin.display(description='Subscription')
    def subscription_link(self, obj):
        return admin_link(PlanSubscription, obj.subscription_id, f'#{obj.subscription_id} — {obj.subscription.student.name}') if obj.subscription_id else 'Unmatched / not linked'

    @admin.display(description='Request fields (signature excluded)')
    def safe_request(self, obj):
        return pretty_summary(obj.request_summary)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PlanSubscriptionCourse)
class PlanSubscriptionCourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'subscription', 'course', 'created_at')
    list_filter = ('course', 'subscription__payment_status', 'created_at')
    search_fields = ('subscription__student__name', 'subscription__student__user__username', 'course__name')
    list_select_related = ('subscription__student', 'subscription__plan', 'course')
    raw_id_fields = ('subscription', 'course')
    readonly_fields = ('created_at',)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.subscription.is_paid:
            return ('subscription', 'course', 'created_at')
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.subscription.is_paid:
            return False
        return super().has_delete_permission(request, obj)
