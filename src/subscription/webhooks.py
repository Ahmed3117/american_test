from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import PlanSubscription


@api_view(["POST"])
@permission_classes([AllowAny])
def easypay_webhook(request, api_key=None):
    data = request.data
    invoice_uid = data.get("invoice_uid") or data.get("invoiceUid")
    invoice_sequence = data.get("invoice_sequence") or data.get("invoiceSequence")
    payment_status = str(data.get("payment_status") or data.get("status") or "").lower()

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
