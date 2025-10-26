import requests
import uuid
from django.conf import settings
import json
import logging


logger = logging.getLogger(__name__)

def create_payment(given_id, amount, currency, description, token, metadata=None):
    """
    إنشاء دفعة باستخدام Tokenization
    """
    url = "https://api.moyasar.com/v1/payments"

    payload = {
        "amount": amount,
        "currency": currency,
        "description": description,
        "callback_url": "https://alc-production-5d34.up.railway.app/payments/callback/",
        "metadata": metadata or {},
        "source": {
            "type": "token",
            "token": token
        }
    }

    try:
        logger.info(f"🚀 Sending payment to Moyasar: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            url,
            auth=(settings.MOYASAR_SECRET_KEY, ""),
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=30
        )
        
        logger.info(f"📥 Moyasar Response Status: {response.status_code}")
        logger.info(f"📥 Moyasar Response Body: {response.text}")
        
        return response.json(), response.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Moyasar API Error: {e}", exc_info=True)
        return {
            "error": str(e),
            "message": "Failed to connect to Moyasar API"
        }, 500

def fetch_payment(payment_id):
    url = f"https://api.moyasar.com/v1/payments/{payment_id}"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Basic {settings.MOYASAR_SECRET_KEY}',
    }
    response = requests.get(
            url,
            auth=(settings.MOYASAR_SECRET_KEY, ""),  # Basic Auth: key + empty password
    )    
    return response.json(), response.status_code


def list_payments():
    """
    جلب كل الدفعات من Moyasar
    """
    url = "https://api.moyasar.com/v1/payments"
    
    try:
        response = requests.get(
            url,
            auth=(settings.MOYASAR_SECRET_KEY, ""),  # Basic Auth: secret key + empty password
            headers={"Accept": "application/json"}
        )
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def refund_payment(payment_id, amount=None):
    """
    يرجع مبلغ جزئي أو كامل للعميل.
    - payment_id: رقم العملية في Moyasar
    - amount: المبلغ اللي عايز ترجعه (اختياري، لو مش محدد هيرجع كامل المبلغ)
    """
    url = f"https://api.moyasar.com/v1/payments/{payment_id}/refund"
    payload = {}
    if amount:
        payload["amount"] = amount

    response = requests.post(
        url,
        auth=(settings.MOYASAR_SECRET_KEY, ""),  # Basic Auth: key + empty password
    
        data=json.dumps(payload)
    )

    return response.json()