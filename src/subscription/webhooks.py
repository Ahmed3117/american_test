import logging
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from services.customer_profile import get_customer_profile
from services.easypay_service import easypay_service

from .models import EasyPayWebhookEvent, PlanSubscription

logger = logging.getLogger(__name__)
SUCCESS_STATUSES = {"paid", "success", "successful", "completed"}


def _audit_reply(data, response, *, status=200, outcome, reason='', subscription=None, signature_valid=None):
    """Persist bounded, allowlisted diagnostics; never store the signature here."""
    def scalar(*keys, limit=120):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else None
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                return str(value)[:limit]
        return ''

    summary = {
        'easy_pay_sequence': scalar('easy_pay_sequence', 'invoice_sequence', 'invoiceSequence'),
        'invoice_uid': scalar('invoice_uid', 'invoiceUid'),
        'status': scalar('status', 'payment_status', limit=40),
        'amount': scalar('amount', limit=64),
        'customer_phone': scalar('customer_phone', limit=30),
    }
    EasyPayWebhookEvent.objects.create(
        subscription=subscription, sequence=summary['easy_pay_sequence'],
        invoice_uid=summary['invoice_uid'], provider_status=summary['status'],
        amount=summary['amount'], customer_phone=summary['customer_phone'],
        outcome=outcome, http_status=status, reason=reason[:255],
        signature_present=bool(isinstance(data, dict) and (data.get('signature') or data.get('Signature'))),
        signature_valid=signature_valid, request_summary=summary,
    )
    return Response(response, status=status)


class EasyPayWebhookSerializer(serializers.Serializer):
    signature = serializers.CharField(max_length=128)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    customer_phone = serializers.CharField(max_length=30)
    easy_pay_sequence = serializers.CharField(max_length=120)
    status = serializers.CharField(max_length=40)
    invoice_uid = serializers.CharField(max_length=120, required=False)


@api_view(["POST"])
@permission_classes([AllowAny])
def easypay_webhook(request, api_key=None):
    try:
        return _handle_webhook(request)
    except ParseError:
        return _audit_reply({}, {'success': False, 'error': 'Malformed JSON'}, status=400,
                            outcome=EasyPayWebhookEvent.Outcome.REJECTED, reason='Malformed JSON')
    except Exception:
        # _handle_webhook's transaction has exited/rolled back here. Do not
        # acknowledge payment when processing or its audit write failed.
        logger.error('EasyPay webhook processing failed; inspect server/database health')
        try:
            return _audit_reply(getattr(request, '_full_data', {}), {'success': False, 'error': 'Webhook processing failed'}, status=503,
                                outcome=EasyPayWebhookEvent.Outcome.ERROR, reason='Processing failed; transaction rolled back')
        except Exception:
            logger.error('EasyPay webhook delivery audit could not be persisted')
            return Response({'success': False, 'error': 'Webhook processing failed'}, status=503)


def _handle_webhook(request):
    data = request.data
    if not isinstance(data, dict):
        return _audit_reply({}, {"success": False, "error": "Expected a JSON object"}, status=400,
                            outcome=EasyPayWebhookEvent.Outcome.REJECTED, reason='Expected a JSON object')

    # Missing identifiers must never become a NULL database lookup.
    normalized = {
        "signature": data.get("signature") or data.get("Signature"),
        "amount": data.get("amount"),
        "customer_phone": data.get("customer_phone"),
        "easy_pay_sequence": data.get("easy_pay_sequence") or data.get("invoice_sequence") or data.get("invoiceSequence"),
        "status": data.get("status") or data.get("payment_status"),
    }
    invoice_uid = data.get("invoice_uid") or data.get("invoiceUid")
    if invoice_uid is not None:
        normalized["invoice_uid"] = invoice_uid
    serializer = EasyPayWebhookSerializer(data=normalized)
    if not serializer.is_valid():
        logger.warning("EasyPay webhook rejected: invalid payload fields=%s", sorted(serializer.errors))
        return _audit_reply(data, {"success": False, "errors": serializer.errors}, status=400,
                            outcome=EasyPayWebhookEvent.Outcome.REJECTED,
                            reason='Invalid fields: ' + ', '.join(sorted(serializer.errors)))
    values = serializer.validated_data
    sequence = values["easy_pay_sequence"]
    amount = f'{values["amount"]:.2f}'
    phone = values["customer_phone"]
    payment_status = values["status"].lower()
    if not easypay_service.secret_key:
        logger.error("EasyPay webhook rejected: signing secret not configured")
        return _audit_reply(data, {"success": False, "error": "Webhook is not configured"}, status=503,
                            outcome=EasyPayWebhookEvent.Outcome.CONFIG_ERROR, reason='Signing secret not configured')
    if not easypay_service.verify_webhook_signature(amount, phone, values["signature"]):
        logger.warning("EasyPay webhook rejected: invalid signature sequence=%s", sequence)
        return _audit_reply(data, {"success": False, "error": "Invalid signature"}, status=400,
                            outcome=EasyPayWebhookEvent.Outcome.REJECTED, reason='Invalid signature', signature_valid=False)

    with transaction.atomic():
        matches = PlanSubscription.objects.select_for_update().select_related(
            "plan", "student__user"
        ).filter(easypay_invoice_sequence=sequence)
        if "invoice_uid" in values:
            matches = matches.filter(easypay_invoice_uid=values["invoice_uid"])
        subscriptions = list(matches[:2])
        if not subscriptions:
            logger.warning("EasyPay webhook unmatched: sequence=%s", sequence)
            return _audit_reply(data, {"success": False, "matched": False, "error": "Invoice not found"}, status=404,
                                outcome=EasyPayWebhookEvent.Outcome.UNMATCHED, reason='No saved matching invoice', signature_valid=True)
        if len(subscriptions) != 1:
            logger.error("EasyPay webhook rejected: ambiguous sequence=%s", sequence)
            return _audit_reply(data, {"success": False, "error": "Ambiguous invoice sequence"}, status=409,
                                outcome=EasyPayWebhookEvent.Outcome.AMBIGUOUS, reason='Multiple matching invoices', signature_valid=True)
        subscription = subscriptions[0]
        if values["amount"] != subscription.invoice_amount:
            logger.warning("EasyPay webhook rejected: amount mismatch subscription_id=%s", subscription.id)
            return _audit_reply(data, {"success": False, "error": "Amount does not match invoice"}, status=400,
                                outcome=EasyPayWebhookEvent.Outcome.REJECTED, reason='Amount does not match invoice',
                                subscription=subscription, signature_valid=True)
        # Use the same phone selection/formatting as invoice creation.
        if phone != get_customer_profile(subscription.student)["phone"]:
            logger.warning("EasyPay webhook rejected: phone mismatch subscription_id=%s", subscription.id)
            return _audit_reply(data, {"success": False, "error": "Phone does not match invoice"}, status=400,
                                outcome=EasyPayWebhookEvent.Outcome.REJECTED, reason='Phone does not match invoice',
                                subscription=subscription, signature_valid=True)

        subscription.easypay_payload = dict(data)
        subscription.save(update_fields=["easypay_payload", "updated_at"])
        if payment_status in SUCCESS_STATUSES:
            already_paid = subscription.payment_status == PlanSubscription.PAYMENT_PAID
            if subscription.payment_status != PlanSubscription.PAYMENT_PAID:
                subscription.mark_paid()
            logger.info("EasyPay webhook applied: subscription_id=%s sequence=%s", subscription.id, sequence)
            return _audit_reply(data, {"success": True, "subscription_id": subscription.id}, subscription=subscription,
                                outcome=(EasyPayWebhookEvent.Outcome.ALREADY_PAID if already_paid else EasyPayWebhookEvent.Outcome.PAID),
                                reason='Already paid; no reactivation' if already_paid else 'Payment applied', signature_valid=True)
        logger.info("EasyPay webhook received without payment activation: subscription_id=%s", subscription.id)
        return _audit_reply(data, {"success": True, "matched": True}, subscription=subscription,
                            outcome=EasyPayWebhookEvent.Outcome.RECEIVED, reason='Non-success provider status; no activation', signature_valid=True)
