import requests
import uuid
from django.conf import settings
import json

def create_payment(given_id, amount, currency="SAR", description=None, callback_url=None, source_type=None, metadata=None):
    """
    إنشاء دفعة جديدة في Moyasar
    """
    url = "https://api.moyasar.com/v1/payments"
    
    # تأكد إن المبلغ ينتهي بـ 0 للريال السعودي
    if currency == "SAR" and amount % 10 != 0:
        amount = (amount // 10) * 10
    
    payload = {
        "amount": amount,
        "currency": currency,
        "description": description or "Payment",
        "callback_url": callback_url or "https://alc-production-8568.up.railway.app/payments/callback/",
        "source": {
            "type": source_type or "creditcard"  # القيمة الافتراضية creditcard
        },
        "metadata": metadata or {}
    }
    
    # إضافة given_id فقط لو موجود
    if given_id:
        payload["given_id"] = str(given_id)

    try:
        response = requests.post(
            url,
            auth=(settings.MOYASAR_SECRET_KEY, ""),  # Basic Auth
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json=payload
        )
        
        return response.json()
    
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


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