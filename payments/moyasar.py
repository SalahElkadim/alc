import requests
import uuid
from django.conf import settings
import json

def create_payment(given_id, amount, currency, description, token, metadata=None):
    """
    إنشاء دفعة باستخدام Tokenization
    
    Args:
        given_id: معرف فريد للدفعة (يمكن استخدامه لتتبع الطلب)
        amount: المبلغ بالهللة (100 ريال = 10000 هللة)
        currency: العملة (SAR)
        description: وصف الدفعة
        token: Token من Moyasar SDK
        metadata: بيانات إضافية (اختيارية)
    
    Returns:
        tuple: (response_json, status_code)
    """
    url = "https://api.moyasar.com/v1/payments"

    payload = {
        "given_id": given_id,  # ✅ استخدام الـ parameter المُمرر
        "amount": 10000,
        "currency": currency,
        "description": description,
        "callback_url": "https://alc-production-5d34.up.railway.app/payment/callback/",  # استخدام الـ domain من settings
        "metadata": metadata or {},
        "source": {
            "type": "token",
            "token": token
        }
    }

    try:
        response = requests.post(
            url,
            auth=(settings.MOYASAR_SECRET_KEY, ""),
            json=payload,
            timeout=30  # إضافة timeout لتجنب التعليق
        )
        return response.json(), response.status_code
    
    except requests.exceptions.RequestException as e:
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