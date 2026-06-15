import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from services.easypay_service import easypay_service

from .models import PlanSubscription

logger = logging.getLogger(__name__)


def _extract_amount(data):
    raw = data.get("amount") or data.get("payment_amount")
    if raw is None:
        item = (data.get("items") or [{}])[0]
        raw = item.get("price") or item.get("amount")
    try:
        return f"{float(raw):.2f}"
    except (TypeError, ValueError):
        return None


def _extract_phone(data):
    customer = data.get("customer") or {}
    return (
        data.get("customer_phone")
        or data.get("phone")
        or customer.get("phone")
        or customer.get("mobile")
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def easypay_webhook(request, api_key=None):
    data = request.data or {}
    invoice_uid = data.get("invoice_uid") or data.get("invoiceUid")
    invoice_sequence = data.get("invoice_sequence") or data.get("invoiceSequence")
    payment_status = str(data.get("payment_status") or data.get("status") or "").lower()
    received_signature = data.get("signature") or data.get("Signature")

    if received_signature:
        amount = _extract_amount(data)
        phone = _extract_phone(data)
        if not amount or not phone:
            logger.warning("EasyPay webhook signature missing amount/phone; rejecting")
            return Response({"success": False, "error": "Invalid signature payload"}, status=400)
        if not easypay_service.verify_webhook_signature(amount, phone, received_signature):
            logger.warning("EasyPay webhook signature mismatch for invoice %s", invoice_uid)
            return Response({"success": False, "error": "Invalid signature"}, status=400)

    subscription = PlanSubscription.objects.filter(
        easypay_invoice_uid=invoice_uid,
        easypay_invoice_sequence=invoice_sequence,
    ).first()

    if subscription:
        subscription.easypay_payload = data
        subscription.save(update_fields=["easypay_payload", "updated_at"])

    if subscription and payment_status in {"paid", "success", "successful", "completed"}:
        subscription.mark_paid()
        return Response({"success": True, "subscription_id": subscription.id})

    return Response({"success": True, "matched": bool(subscription)})
