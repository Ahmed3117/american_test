"""Conservative, explicitly confirmed recovery from the old NULL-invoice matcher."""
import hashlib
import json
from dataclasses import dataclass

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.db import transaction
from django.db.models import Q

from services.customer_profile import get_customer_profile
from services.easypay_service import easypay_service

from .models import EasyPayWebhookEvent, PlanSubscription
from .webhooks import EasyPayWebhookSerializer, SUCCESS_STATUSES

PREVIEW_SALT = 'subscription.legacy-payment-repair.v1'
PREVIEW_MAX_AGE = 600
BATCH_SIZE = 25


class RepairRejected(ValueError):
    pass


@dataclass
class RepairAssessment:
    source: PlanSubscription
    eligible: bool = False
    reason: str = ''
    owner: PlanSubscription | None = None
    sequence: str = ''


def possible_legacy_misattributions():
    """Old code could only misattribute when BOTH saved identifiers were empty."""
    return PlanSubscription.objects.filter(payment_status=PlanSubscription.PAYMENT_PAID).filter(
        Q(easypay_invoice_uid__isnull=True) | Q(easypay_invoice_uid=''),
        Q(easypay_invoice_sequence__isnull=True) | Q(easypay_invoice_sequence=''),
    ).select_related('student__user', 'plan').prefetch_related('courses').order_by('-updated_at', '-id')


def assess_legacy_payment(source):
    row = RepairAssessment(source=source)

    def review(reason):
        row.reason = reason
        return row

    if source.payment_status != PlanSubscription.PAYMENT_PAID:
        return review('Not an EasyPay-paid record (manual and pending purchases are never reset).')
    if source.easypay_invoice_uid is not None or source.easypay_invoice_sequence is not None:
        return review('Identifiers are not both NULL; not the exact legacy matcher pattern.')
    if source.webhook_events.filter(
        signature_valid=True,
        outcome__in=[EasyPayWebhookEvent.Outcome.PAID, EasyPayWebhookEvent.Outcome.ALREADY_PAID],
    ).exists():
        return review('Verified payment history exists; manual investigation required.')
    data = source.easypay_payload
    if not isinstance(data, dict) or not data.get('easy_pay_sequence'):
        return review('No retained EasyPay callback sequence; insufficient evidence.')
    if any(data.get(key) for key in ('invoice_uid', 'invoiceUid', 'invoice_sequence', 'invoiceSequence')):
        return review('Payload does not match the old missing-identifier callback pattern.')
    serializer = EasyPayWebhookSerializer(data=data)
    if not serializer.is_valid():
        return review('Retained callback fields are incomplete or malformed.')
    values = serializer.validated_data
    row.sequence = values['easy_pay_sequence']
    if values['status'].lower() not in SUCCESS_STATUSES:
        return review('Retained callback is not a successful-payment notification.')
    if not easypay_service.secret_key or not easypay_service.verify_webhook_signature(
        f'{values["amount"]:.2f}', values['customer_phone'], values['signature'],
    ):
        return review('Retained signature cannot be verified with the current key; do not guess.')
    owners = list(PlanSubscription.objects.filter(
        easypay_invoice_sequence=row.sequence,
    ).select_related('student__user', 'plan').order_by('pk')[:2])
    if len(owners) != 1 or owners[0].pk == source.pk or not owners[0].easypay_invoice_uid:
        return review('Cannot identify one different purchase with complete matching invoice identifiers.')
    row.owner = owners[0]
    if values['amount'] != row.owner.invoice_amount or values['customer_phone'] != get_customer_profile(row.owner.student)['phone']:
        return review('Callback amount/phone does not match the identified purchase; manual reconciliation required.')
    # A later callback can overwrite an already-paid purchase's last payload.
    # Never assume that last payload explains an earlier paid transition.
    if not source.paid_at or abs((source.updated_at - source.paid_at).total_seconds()) > 60:
        return review('Paid-at and last update do not identify the same payment transition; an earlier legitimate payment cannot be ruled out.')
    content_type = ContentType.objects.get_for_model(PlanSubscription)
    if LogEntry.objects.filter(content_type=content_type, object_id=str(source.pk), action_flag=CHANGE).exists():
        # Avoid interpreting translated or custom admin change messages as proof
        # that a payment status was never deliberately set by an administrator.
        return review('Administrator change history exists; inspect earlier payment decisions manually.')
    row.eligible = True
    row.reason = 'Verified retained callback belongs to another uniquely matched invoice; source has no invoice or verified payment evidence.'
    return row


def _fingerprint(row):
    source, owner = row.source, row.owner
    evidence = {
        'source': source.pk, 'status': source.payment_status,
        'paid_at': source.paid_at, 'updated_at': source.updated_at,
        'student': source.student_id, 'plan': source.plan_id,
        'uid': source.easypay_invoice_uid, 'sequence': source.easypay_invoice_sequence,
        'amount': source.invoice_amount, 'phone': get_customer_profile(source.student)['phone'],
        'courses': sorted(course.pk for course in source.courses.all()),
        'payload': source.easypay_payload,
        'owner': owner.pk, 'owner_updated_at': owner.updated_at,
        'owner_uid': owner.easypay_invoice_uid, 'owner_sequence': owner.easypay_invoice_sequence,
        'owner_amount': owner.invoice_amount, 'owner_phone': get_customer_profile(owner.student)['phone'],
    }
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()


def make_repair_preview(row, actor):
    if not row.eligible:
        raise RepairRejected('This record is for manual review only.')
    return signing.dumps({'source': row.source.pk, 'owner': row.owner.pk,
                          'actor': actor.pk, 'fingerprint': _fingerprint(row)}, salt=PREVIEW_SALT, compress=True)


@transaction.atomic
def repair_selected_payments(tokens, *, actor, reason):
    if not (actor.is_active and actor.is_staff and actor.is_superuser):
        raise RepairRejected('Only active staff superusers may repair payments.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise RepairRejected('A reconciliation reason (up to 500 characters) is required.')
    if not tokens or len(tokens) > BATCH_SIZE:
        raise RepairRejected(f'Select between 1 and {BATCH_SIZE} reviewed records.')
    previews = []
    for token in tokens:
        try:
            if not isinstance(token, str) or len(token) > 2048:
                raise ValueError
            preview = signing.loads(token, salt=PREVIEW_SALT, max_age=PREVIEW_MAX_AGE)
            if (preview['actor'] != actor.pk or type(preview['source']) is not int
                    or type(preview['owner']) is not int or preview['source'] <= 0 or preview['owner'] <= 0
                    or not isinstance(preview['fingerprint'], str) or len(preview['fingerprint']) != 64):
                raise ValueError
            previews.append(preview)
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            raise RepairRejected('Invalid or expired preview. Refresh and review again.') from None
    source_ids = [item['source'] for item in previews]
    if len(set(source_ids)) != len(source_ids):
        raise RepairRejected('Duplicate selections are not allowed.')
    ids = sorted({item[key] for item in previews for key in ('source', 'owner')})
    # Lock only the subscription rows, without nullable joins; compatible with PostgreSQL.
    locked = list(PlanSubscription.objects.select_for_update().filter(pk__in=ids).order_by('pk').values_list('pk', flat=True))
    if locked != ids:
        raise RepairRejected('A reviewed purchase was removed. Refresh the preview.')
    rows = []
    for preview in previews:
        source = PlanSubscription.objects.select_related('student__user', 'plan').prefetch_related('courses').get(pk=preview['source'])
        row = assess_legacy_payment(source)
        if not row.eligible or row.owner.pk != preview['owner'] or _fingerprint(row) != preview['fingerprint']:
            raise RepairRejected('Evidence changed or is no longer safe. Nothing was reset; refresh and review again.')
        rows.append(row)
    content_type = ContentType.objects.get_for_model(PlanSubscription)
    for row in rows:
        source = row.source
        audit = {'previous_payment_status': source.payment_status, 'previous_paid_at': source.paid_at.isoformat(),
                 'previous_updated_at': source.updated_at.isoformat(), 'matched_other_subscription': row.owner.pk,
                 'callback_sequence': row.sequence, 'preserved_course_ids': sorted(course.pk for course in source.courses.all()),
                 'evidence_fingerprint': _fingerprint(row)}
        source.payment_status = PlanSubscription.PAYMENT_PENDING
        source.paid_at = None
        source.save(update_fields=['payment_status', 'paid_at', 'updated_at'])
        LogEntry.objects.create(
            user=actor, content_type=content_type, object_id=str(source.pk), object_repr=str(source)[:200], action_flag=CHANGE,
            change_message='Legacy webhook payment_status repair to pending. Reason: ' + reason.strip()
                           + '. Evidence (no signatures): ' + json.dumps(audit, sort_keys=True),
        )
    return len(rows)
