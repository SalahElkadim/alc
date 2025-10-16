from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from .moyasar import create_payment
import requests
from rest_framework.decorators import api_view
from django.conf import settings
from .models import Payment, Invoice
from .serializers import PaymentSerializer, InvoiceSerializer, InvoiceDetailSerializer
from .moyasar import fetch_payment as fetch_payment_api
from .moyasar import list_payments, refund_payment
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
import uuid
from django.utils import timezone
from django.http import Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import logging
from decimal import Decimal
from django.db import transaction

logger = logging.getLogger(__name__)
class CreatePaymentView(APIView):
    """
    إنشاء عملية دفع جديدة في Live Mode باستخدام Payment Intent
    """
    #permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data

            # تأكد من وجود المبلغ والوصف
            amount = data.get("amount", 10000)  # بالهللة (100 ريال)
            description = data.get("description", "فتح الكتب")
            callback_url = data.get("callback_url", "https://alc-production-5d34.up.railway.app/payments/callback/")

            if not amount:
                return Response({"error": "المبلغ مطلوب"}, status=400)

            # نرسل فقط المعلومات الضرورية إلى Moyasar
            # استخدم payment intent بدون source للحصول على صفحة دفع
            payment_response = create_payment(
                given_id=request.user.id,
                amount=amount,
                description=description,
                currency="SAR",
                callback_url=callback_url,
                metadata={"user": user.email}
                # لا ترسل source على الإطلاق!
            )

            if "id" not in payment_response:
                return Response({
                    "success": False,
                    "error": payment_response
                }, status=400)

            # نخزن الدفع في قاعدة البيانات
            payment, created = Payment.objects.get_or_create(
                user=user,
                moyasar_id=payment_response["id"],
                defaults={
                    "amount": payment_response.get("amount"),
                    "status": payment_response.get("status"),
                    "description": description,
                }
            )

            # إنشاء فاتورة مرتبطة
            if created:
                self.create_invoice_for_payment(payment, description)

            # نرجع رابط الدفع للعميل
            # Moyasar بترجع checkout_url عشان توجه المستخدم للدفع
            payment_url = f"https://moyasar.com/checkouts/{payment_response['id']}"

            return Response({
                "success": True,
                "payment_url": payment_url,
                "payment_id": payment_response["id"],
                "status": payment_response["status"]
            })

        except Exception as e:
            logger.error(f"Error in CreatePaymentView: {str(e)}")
            return Response({
                "success": False,
                "error": str(e)
            }, status=500)

    def create_invoice_for_payment(self, payment, description=None):
        """إنشاء فاتورة عند إنشاء الدفعة"""
        invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        invoice = Invoice.objects.create(
            payment=payment,
            invoice_number=invoice_number,
            amount=Decimal(payment.amount) / 100,
            currency='SAR',
            description=description or f"Payment for {payment.moyasar_id}",
        )
        return invoice

@csrf_exempt
@require_POST
def moyasar_webhook(request):
    """
    Webhook endpoint لاستقبال التحديثات من Moyasar
    """
    try:
        # التحقق من صحة الـ webhook (اختياري)
        signature = request.headers.get('X-Moyasar-Signature')
        if not verify_webhook_signature(request.body, signature):
            logger.warning("Invalid webhook signature")
            # نكمل المعالجة حتى لو فشل التحقق

        payload = json.loads(request.body)
        event_type = payload.get('type')
        payment_data = payload.get('data', {})
        
        logger.info(f"Received webhook: {event_type} for payment {payment_data.get('id')}")

        if event_type == 'payment_paid':
            handle_payment_paid(payment_data)
        elif event_type == 'payment_failed':
            handle_payment_failed(payment_data)
        elif event_type == 'payment_refunded':
            handle_payment_refunded(payment_data)

        return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return HttpResponse("Error", status=200)  # نرجع 200 لمنع إعادة الإرسال


def verify_webhook_signature(payload, signature):
    """
    التحقق من صحة الـ webhook signature
    """
    try:
        if not signature or not hasattr(settings, 'MOYASAR_WEBHOOK_SECRET'):
            return True  # تجاهل التحقق إذا لم يكن الـ secret محدد
        
        import hmac
        import hashlib
        
        expected_signature = hmac.new(
            settings.MOYASAR_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {str(e)}")
        return True  # نسمح بالمرور في حالة الخطأ


def handle_payment_paid(payment_data):
    """
    معالجة حدث الدفع المكتمل
    """
    moyasar_id = payment_data.get('id')
    
    try:
        with transaction.atomic():
            payment = Payment.objects.get(moyasar_id=moyasar_id)
            payment.status = 'paid'
            payment.amount = payment_data.get('amount', payment.amount)
            payment.paid_at = timezone.now()
            payment.save()

            # تحديث الفاتورة
            update_invoice_on_payment_success(payment)
            
            logger.info(f"Payment {moyasar_id} marked as paid via webhook")
            
    except Payment.DoesNotExist:
        logger.warning(f"Payment {moyasar_id} not found in database")
    except Exception as e:
        logger.error(f"Error handling payment_paid webhook: {str(e)}")


def handle_payment_failed(payment_data):
    """
    معالجة حدث فشل الدفع
    """
    moyasar_id = payment_data.get('id')
    
    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        payment.status = 'failed'
        payment.save()
        logger.info(f"Payment {moyasar_id} marked as failed via webhook")
        
    except Payment.DoesNotExist:
        logger.warning(f"Payment {moyasar_id} not found in database")
    except Exception as e:
        logger.error(f"Error handling payment_failed webhook: {str(e)}")


def handle_payment_refunded(payment_data):
    """
    معالجة حدث إرجاع المبلغ
    """
    moyasar_id = payment_data.get('id')
    
    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        payment.status = 'refunded'
        payment.save()
        logger.info(f"Payment {moyasar_id} marked as refunded via webhook")
        
    except Payment.DoesNotExist:
        logger.warning(f"Payment {moyasar_id} not found in database")
    except Exception as e:
        logger.error(f"Error handling payment_refunded webhook: {str(e)}")


def update_invoice_on_payment_success(payment):
    """
    تحديث الفاتورة عند نجاح الدفع
    """
    try:
        invoice = payment.invoice
        if not invoice.paid_at:  # لو لم يتم تحديثها من قبل
            invoice.paid_at = timezone.now()
            invoice.status = 'paid'
            invoice.save()
            logger.info(f"Invoice {invoice.invoice_number} marked as paid")
    except Invoice.DoesNotExist:
        logger.warning(f"No invoice found for payment {payment.moyasar_id}")
    except Exception as e:
        logger.error(f"Error updating invoice for payment {payment.moyasar_id}: {str(e)}")


@csrf_exempt
def payment_callback_view(request):
    """
    Callback URL لإعادة توجيه المستخدم بعد الدفع
    """
    try:
        status = request.GET.get("status")
        moyasar_id = request.GET.get("id")

        payment = None
        invoice = None

        if moyasar_id:
            try:
                payment = Payment.objects.get(moyasar_id=moyasar_id)
                invoice = getattr(payment, "invoice", None)
                
                # تحديث حالة الدفع من Moyasar
                payment_data, status_code = fetch_payment_api(moyasar_id)
                if status_code == 200:
                    old_status = payment.status
                    payment.status = payment_data.get("status")
                    payment.save()
                    
                    # إذا تم الدفع بنجاح، نحدث الفاتورة
                    if old_status != "paid" and payment.status == "paid":
                        update_invoice_on_payment_success(payment)
                        
            except Payment.DoesNotExist:
                logger.warning(f"Payment {moyasar_id} not found in callback")

        if status == "paid" and payment:
            return render(request, "payments/payment_success.html", {
                "payment": payment,
                "invoice": invoice,
            })
        else:
            return render(request, "payments/payment_failed.html", {
                "payment": payment,
                "status": status,
                "moyasar_id": moyasar_id,
            })

    except Exception as e:
        logger.error(f"Error in payment_callback_view: {str(e)}")
        return render(request, "payments/payment_failed.html", {
            "error": "حدث خطأ في معالجة الدفعة"
        })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_detail_view(request, moyasar_id):
    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        invoice = payment.invoice
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data)
    except Payment.DoesNotExist:
        return Response({"error": "Payment not found"}, status=404)
    except Invoice.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=404)
    except Exception as e:
        logger.error(f"Error in invoice_detail_view: {str(e)}")
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_invoices_view(request):
    """
    تعرض كل الفواتير الموجودة في النظام
    """
    try:
        invoices = Invoice.objects.all().order_by('-created_at')
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Error in all_invoices_view: {str(e)}")
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_invoices_view(request):
    """
    تعرض فواتير المستخدم الحالي فقط
    """
    try:
        user_payments = Payment.objects.filter(user=request.user)
        invoices = Invoice.objects.filter(payment__in=user_payments).order_by('-created_at')
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Error in user_invoices_view: {str(e)}")
        return Response({"error": str(e)}, status=500)


@csrf_exempt
def display_invoice_view(request, moyasar_id):
    """
    عرض الفاتورة في صفحة HTML جميلة
    """
    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        invoice = payment.invoice
        
        return render(request, 'payments/invoice_display.html', {
            'invoice': invoice,
            'payment': payment,
        })
        
    except Payment.DoesNotExist:
        return render(request, 'payments/invoice_not_found.html', {
            'error': 'الدفعة غير موجودة'
        })
    except Invoice.DoesNotExist:
        return render(request, 'payments/invoice_not_found.html', {
            'error': 'الفاتورة غير موجودة'
        })
    except Exception as e:
        logger.error(f"Error in display_invoice_view: {str(e)}")
        return render(request, 'payments/invoice_not_found.html', {
            'error': 'حدث خطأ في عرض الفاتورة'
        })


# إضافة view بسيط للاختبار
@csrf_exempt
def test_callback_view(request):
    """
    View بسيط لاختبار الـ callback
    """
    return HttpResponse("Callback test successful", status=200)