import hashlib
import logging

import requests
from django.conf import settings
from django.utils import timezone

from services.customer_profile import get_customer_profile
from services.easypay_service import easypay_service

logger = logging.getLogger(__name__)


def create_plan_subscription_invoice(subscription):
    if not easypay_service.vendor_code or not easypay_service.secret_key:
        return {
            "success": False,
            "error": "EasyPay credentials are not configured.",
        }

    profile_source = type("ProfileSource", (), {"user": subscription.student.user, "id": subscription.id})()
    profile = get_customer_profile(profile_source)
    amount = f"{subscription.invoice_amount:.2f}"
    profile_id = f"plan-subscription-{subscription.id}"
    signature = hashlib.sha256(
        f"{easypay_service.vendor_code}{easypay_service.secret_key}{amount}{profile_id}{profile['phone']}".encode("utf-8")
    ).hexdigest()

    payload = {
        "vendor_code": easypay_service.vendor_code,
        "amount": amount,
        "payment_expiry": int(timezone.now().timestamp() * 1000) + easypay_service.payment_expiry,
        "payment_method": easypay_service.payment_method,
        "signature": signature,
        "customer": {
            "name": profile["full_name"],
            "phone": profile["phone"],
            "profile_id": profile_id,
        },
        "items": [
            {
                "item_id": str(subscription.id),
                "price": amount,
                "quantity": 1,
                "description": subscription.plan.title,
            }
        ],
    }
    if easypay_service.webhook_url:
        payload["webhook_url"] = easypay_service.webhook_url

    try:
        response = requests.post(
            easypay_service.create_invoice_url,
            headers=easypay_service.headers,
            json=payload,
            timeout=(5, 12),
        )
        if response.status_code not in [200, 201]:
            return {"success": False, "error": response.text[:200]}

        data = response.json()
        invoice_uid = data.get("invoice_uid")
        invoice_sequence = data.get("invoice_sequence")
        if not invoice_uid or not invoice_sequence:
            return {"success": False, "error": "EasyPay response missed invoice identifiers."}

        payment_url = f"{settings.EASYPAY_INVOICE_URL}/{invoice_uid}/{invoice_sequence}"
        subscription.easypay_invoice_uid = invoice_uid
        subscription.easypay_invoice_sequence = invoice_sequence
        subscription.easypay_payment_url = payment_url
        subscription.easypay_payload = data
        subscription.save(
            update_fields=[
                "easypay_invoice_uid",
                "easypay_invoice_sequence",
                "easypay_payment_url",
                "easypay_payload",
                "updated_at",
            ]
        )
        return {"success": True, "payment_url": payment_url, "data": data}
    except requests.RequestException as exc:
        logger.exception("EasyPay plan subscription invoice failed")
        return {"success": False, "error": str(exc)}
