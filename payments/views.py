from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from .models import Payment
from .serializers import CreatePaymentSerializer, PaymentStatusSerializer
from .services import MoyasarService
import uuid
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
import logging

logger = logging.getLogger(__name__)

class CreatePaymentView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        serializer = CreatePaymentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # استخراج البيانات
        amount = serializer.validated_data['amount']
        description = serializer.validated_data['description']
        customer_data = {
            'name': serializer.validated_data.get('customer_name', 'Card Holder'),
            'email': serializer.validated_data.get('customer_email', ''),
            'phone': serializer.validated_data.get('customer_phone', ''),
        }
        
        # إنشاء payment form (سيتطلب إكمال من المستخدم)
        moyasar_response = MoyasarService.create_payment(
            amount=amount,
            description=description,
            customer_data={
                "customer_name": customer_data['name'],
                "customer_email": customer_data['email'],
                "customer_phone": customer_data['phone'],
            }
        )
        
        if not moyasar_response:
            return Response({
                'success': False,
                'message': 'فشل في إنشاء عملية الدفع مع بوابة الدفع'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # حفظ في قاعدة البيانات
        try:
            payment = Payment.objects.create(
                moyasar_payment_id=moyasar_response['id'],
                amount=amount,
                description=description,
                customer_name=customer_data['name'],
                customer_email=customer_data['email'],
                customer_phone=customer_data['phone'],
                status=moyasar_response.get('status', 'initiated'),
                user=request.user if request.user.is_authenticated else None
            )
            
            return Response({
                'success': True,
                'payment_id': payment.id,
                'payment_url': moyasar_response.get('source', {}).get('transaction_url'),  # 🔥 الحل هنا
                'moyasar_payment_id': moyasar_response['id'],
                'status': moyasar_response.get('status'),
                'message': 'تم إنشاء عملية الدفع بنجاح'
            })
            
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            return Response({
                'success': False,
                'message': 'فشل في حفظ بيانات الدفع'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PaymentStatusView(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        
        # تحديث الحالة من Moyasar
        moyasar_data = MoyasarService.get_payment_status(payment.moyasar_payment_id)
        
        if moyasar_data:
            # تحديث حالة الدفع
            old_status = payment.status
            payment.status = moyasar_data['status']
            
            if payment.status == 'paid' and old_status != 'paid':
                payment.paid_at = timezone.now()
            
            payment.save()
        
        serializer = PaymentStatusSerializer(payment)
        return Response({
            'success': True,
            'payment': serializer.data
        })

class PaymentCallbackView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        """
        Webhook من Moyasar عند تغيير حالة الدفع
        """
        payment_data = request.data
        
        try:
            payment = Payment.objects.get(
                moyasar_payment_id=payment_data.get('id')
            )
            
            # تحديث الحالة
            old_status = payment.status
            payment.status = payment_data.get('status', payment.status)
            
            if payment.status == 'paid' and old_status != 'paid':
                payment.paid_at = timezone.now()
            
            payment.save()
            
            return Response({'success': True})
        
        except Payment.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Payment not found'
            }, status=status.HTTP_404_NOT_FOUND)

class PaymentListView(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        payments = Payment.objects.all().order_by('-created_at')
        serializer = PaymentStatusSerializer(payments, many=True)
        return Response({
            'success': True,
            'payments': serializer.data
        })
    

# في views.py أضف هذا الـ view للاختبار
from django.http import JsonResponse
import requests
import base64
import json

class TestMoyasarView(APIView):
    authentication_classes = []
    permission_classes = []
    def get(self, request):
        """
        اختبار Moyasar API مع Credit Card
        """
        
        # بيانات الاختبار الصحيحة حسب الوثائق
        test_payload = {
            "amount": 1000,  # 10 ريال
            "currency": "SAR",
            "description": "Test payment from Django",
            "callback_url": f"{settings.MOYASAR_BASE_URL}/api/callback/",
            "source": {
                "type": "creditcard",
                "name": "Ahmed Ali",
                "number": "4111111111111111",  # Visa test card
                "cvc": "123", 
                "month": 12,
                "year": 2025
            },
            "metadata": {
                "test": "true",
                "environment": "development"
            }
        }
        
        api_key = getattr(settings, 'MOYASAR_API_KEY', 'NOT_SET')
        
        if api_key == 'NOT_SET':
            return Response({
                'success': False,
                'error': 'MOYASAR_API_KEY is not set in settings'
            })
        
        # Authentication
        auth_string = f"{api_key}:"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        try:
            url = "https://api.moyasar.com/v1/payments"
            response = requests.post(url, json=test_payload, headers=headers, timeout=30)
            
            response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            
            return Response({
                'success': response.status_code == 201,
                'moyasar_status_code': response.status_code,
                'moyasar_response': response_data,
                'request_payload': test_payload,
                'payment_url': response_data.get('source', {}).get('transaction_url') if response.status_code == 201 else None,
                'payment_id': response_data.get('id') if response.status_code == 201 else None,
                'payment_status': response_data.get('status') if response.status_code == 201 else None
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            })