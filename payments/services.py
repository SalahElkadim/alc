# services.py - النسخة الكاملة مع جميع الدوال
import requests
import base64
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
class MoyasarService:
    authentication_classes = []
    permission_classes = []
    @staticmethod
    def create_payment(amount, description, customer_data=None):
        """
        إنشاء payment مع Moyasar - حسب الوثائق الرسمية
        """
        
        # التحقق من المتطلبات
        api_key = getattr(settings, 'MOYASAR_API_KEY', None)
        if not api_key:
            logger.error("MOYASAR_API_KEY is not configured")
            return None
        
        # إعداد البيانات للـ Credit Card payment
        payload = {
            "amount": int(amount),
            "currency": "SAR",
            "description": str(description),
            "callback_url": f"{settings.MOYASAR_BASE_URL}/api/callback/",
            "source": {
                "type": "creditcard",  # النوع المطلوب
                "name": customer_data.get('name', 'Card Holder') if customer_data else 'Card Holder',
                "number": "4111111111111111",  # Test card number
                "cvc": "123",
                "month": 12,
                "year": 2025
            }
        }
        
        # إضافة metadata للعميل
        if customer_data:
            payload["metadata"] = {
                "customer_name": customer_data.get('name', ''),
                "customer_email": customer_data.get('email', ''),
                "customer_phone": customer_data.get('phone', ''),
            }
        
        # تحضير Authentication
        auth_string = f"{api_key}:"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        url = "https://api.moyasar.com/v1/payments"
        
        try:
            logger.info(f"Sending request to Moyasar: {payload}")
            
            response = requests.post(
                url, 
                json=payload, 
                headers=headers, 
                timeout=30
            )
            
            logger.info(f"Moyasar response: {response.status_code}")
            logger.info(f"Response body: {response.text}")
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"Payment created: {result.get('id')}")
                return result
            else:
                logger.error(f"Moyasar error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return None

    @staticmethod
    def get_payment_status(payment_id):
        """
        الحصول على حالة الدفع من Moyasar
        """
        api_key = getattr(settings, 'MOYASAR_API_KEY', None)
        if not api_key:
            logger.error("MOYASAR_API_KEY is not configured")
            return None
        
        # تحضير Authentication
        auth_string = f"{api_key}:"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        url = f"https://api.moyasar.com/v1/payments/{payment_id}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Payment status retrieved: {result.get('status')}")
                return result
            else:
                logger.error(f"Get payment error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Get payment request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Get payment unexpected error: {str(e)}")
            return None

    @staticmethod
    def create_stcpay_payment(amount, description, phone_number, customer_data=None):
        """
        إنشاء payment مع STC Pay
        """
        
        api_key = getattr(settings, 'MOYASAR_API_KEY', None)
        if not api_key:
            logger.error("MOYASAR_API_KEY is not configured")
            return None
        
        # تنسيق رقم الهاتف
        if not phone_number.startswith('+966'):
            if phone_number.startswith('05'):
                phone_number = '+966' + phone_number[1:]
            elif phone_number.startswith('5'):
                phone_number = '+966' + phone_number
        
        payload = {
            "amount": int(amount),
            "currency": "SAR",
            "description": str(description),
            "callback_url": f"{settings.MOYASAR_BASE_URL}/api/callback/",
            "source": {
                "type": "stcpay",
                "mobile": phone_number,
                "branch": "Online Store",
                "cashier": "Web App"
            }
        }
        
        # إضافة metadata
        if customer_data:
            payload["metadata"] = {
                "customer_name": customer_data.get('name', ''),
                "customer_email": customer_data.get('email', ''),
                "customer_phone": customer_data.get('phone', ''),
            }
        
        # تحضير Authentication
        auth_string = f"{api_key}:"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        url = "https://api.moyasar.com/v1/payments"
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 201:
                result = response.json()
                return result
            else:
                logger.error(f"STC Pay error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"STC Pay error: {str(e)}")
            return None
    
    @staticmethod
    def create_payment_form(amount, description, customer_data=None):
        """
        إنشاء payment يتطلب إكمال من المستخدم
        """
        
        api_key = getattr(settings, 'MOYASAR_API_KEY', None)
        if not api_key:
            return None
        
        # استخدام test credit card للـ initiated payment
        payload = {
            "amount": int(amount),
            "currency": "SAR", 
            "description": str(description),
            "callback_url": f"{settings.MOYASAR_BASE_URL}/api/callback/",
            "source": {
                "type": "creditcard",
                "name": "Test Card Holder",
                "number": "4111111111111111",  # Visa test card
                "cvc": "123",
                "month": 12,
                "year": 2025,
                "manual": False,  # يتطلب 3DS
                "save_card": False
            }
        }
        
        if customer_data:
            payload["metadata"] = customer_data
        
        # Authentication
        auth_string = f"{api_key}:"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                "https://api.moyasar.com/v1/payments", 
                json=payload, 
                headers=headers, 
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                # إضافة URL للـ 3DS challenge إذا كان Payment في حالة initiated
                if result.get('status') == 'initiated':
                    transaction_url = result.get('source', {}).get('transaction_url')
                    if transaction_url:
                        result['payment_url'] = transaction_url
                return result
            else:
                logger.error(f"Payment form error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Payment form error: {str(e)}")
            return None

    @staticmethod
    def refund_payment(payment_id, amount=None):
        """
        استرداد كامل أو جزئي للدفعة
        """
        api_key = getattr(settings, 'MOYASAR_API_KEY', None)
        if not api_key:
            logger.error("MOYASAR_API_KEY is not configured")
            return None
        
        # تحضير Authentication
        auth_string = f"{api_key}:"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        payload = {}
        if amount:
            payload["amount"] = int(amount)
        
        url = f"https://api.moyasar.com/v1/payments/{payment_id}/refund"
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Payment refunded: {payment_id}")
                return result
            else:
                logger.error(f"Refund error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Refund error: {str(e)}")
            return None

    @staticmethod
    def void_payment(payment_id):
        """
        إلغاء الدفعة (للدفعات المُعتمدة وغير المُحصلة)
        """
        api_key = getattr(settings, 'MOYASAR_API_KEY', None)
        if not api_key:
            logger.error("MOYASAR_API_KEY is not configured")
            return None
        
        # تحضير Authentication
        auth_string = f"{api_key}:"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        url = f"https://api.moyasar.com/v1/payments/{payment_id}/void"
        
        try:
            response = requests.post(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Payment voided: {payment_id}")
                return result
            else:
                logger.error(f"Void error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Void error: {str(e)}")
            return None