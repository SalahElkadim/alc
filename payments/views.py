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
from users.models import UserBook
from questions.models import Book



logger = logging.getLogger(__name__)

class CheckValueView(APIView):
    """
    Endpoint يستقبل JWT في الهيدر + قيمة في البادي،
    ويرجع True أو False بناءً على شرط بسيط.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # نقرأ القيمة من البادي
        value = request.data.get("value")

        # شرط بسيط كمثال (تقدر تغيره زي ما تحب)
        if value == "hello":
            return Response({"result": False})
        else:
            return Response({"result": True})
            




def payment_page(request):
    token = request.GET.get("token")
    amount = request.GET.get("amount", 10000)
    book_id = request.GET.get('book_id')

    if not token:
        return render(request, "error.html", {"message": "Missing access token"})

    book = None
    if book_id:
        book = Book.objects.filter(id=book_id).first()
        if book:
            amount = int(book.price_sar * 100)  # تحويل لهللة

    return render(request, "payment.html", {
        "publishable_key": settings.MOYASAR_PUBLISHABLE_KEY,
        "amount": amount,
        "access_token": token,
        'book_id': book_id,  # ✅ نمرر book_id للـ template
        'book': book
    })

def post(self, request):
    try:
        data = request.data
        user = request.user

        # 1️⃣ التحقق من البيانات
        token = data.get("source", {}).get("token")
        book_id = data.get("book_id")

        if not token:
            return Response({"success": False, "error": "Token is required"}, status=400)

        if not book_id:
            return Response({"success": False, "error": "book_id is required"}, status=400)

        # 2️⃣ جلب الكتاب
        book = get_object_or_404(Book, id=book_id)

        # 3️⃣ حساب المبلغ
        amount_halalah = int(book.price_sar * 100)
        description = f"Unlock book: {book.title}"

        # 4️⃣ إنشاء given_id فريد
        given_id = str(uuid.uuid4())

        # 5️⃣ إرسال الدفع لـ Moyasar
        payment_response, status_code = create_payment(
            given_id=given_id,
            amount=amount_halalah,
            currency="SAR",
            description=description,
            token=token,
            metadata={
                "username": user.email,
                "user_id": str(user.id),
                "book_id": str(book.id),
                "given_id": given_id,  # ✅ مهم للتتبع
            }
        )

        logger.info(f"📩 Moyasar Response: {payment_response}")

        # ❌ تحقق من نجاح الطلب قبل الحفظ
        if status_code not in [200, 201]:
            logger.error(f"❌ Moyasar API Error: {payment_response}")
            return Response({
                "success": False,
                "error": payment_response.get("message", "Failed to create payment")
            }, status=status_code)

        # 6️⃣ حفظ الدفع في قاعدة البيانات
        if "id" not in payment_response:
            logger.error(f"❌ No 'id' in Moyasar response: {payment_response}")
            return Response({
                "success": False,
                "error": "Invalid response from payment gateway"
            }, status=500)

        moyasar_id = payment_response["id"]
        
        # ✅ استخدام transaction لضمان الحفظ
        with transaction.atomic():
            payment, created = Payment.objects.get_or_create(
                moyasar_id=moyasar_id,
                defaults={
                    "user": user,
                    "book": book,
                    "amount": amount_halalah,
                    "status": payment_response.get("status", "initiated"),
                    "description": description,
                    "source_type": payment_response.get("source", {}).get("type", "token"),
                }
            )

            if not created:
                # ✅ تحديث البيانات لو الدفع موجود
                payment.status = payment_response.get("status", payment.status)
                payment.save()
                logger.warning(f"⚠️ Payment {moyasar_id} already exists, updated status")

            # 7️⃣ إنشاء الفاتورة
            self.create_invoice(payment, description)
            
            logger.info(f"✅ Payment saved: {moyasar_id} - Status: {payment.status}")

        # 8️⃣ معالجة الحالة
        status = payment_response.get("status")
        moyasar_source = payment_response.get("source", {})

        if status == "initiated":
            return Response({
                "status": "initiated",
                "transaction_url": moyasar_source.get("transaction_url"),
                "payment_id": moyasar_id,  # ✅ مهم للتتبع
                "book": {"id": str(book.id), "title": book.title},
            })
        elif status == "paid":
            unlock_user_book(payment)
            return Response({
                "status": "paid",
                "message": "Book unlocked successfully",
                "payment_id": moyasar_id,
                "book": {"id": str(book.id), "title": book.title},
            })
        else:
            return Response({
                "status": status,
                "message": payment_response.get("message", "Unknown status"),
                "payment_id": moyasar_id,
            }, status=400)

    except Book.DoesNotExist:
        return Response({"success": False, "error": "Book not found"}, status=404)
    except Exception as e:
        logger.error(f"❌ Error in CreatePaymentView: {e}", exc_info=True)
        return Response({
            "success": False,
            "error": str(e)
        }, status=500)
    

@api_view(["GET"])
def fetch_payment_view(request, moyasar_id):
    try:
        data, status_code = fetch_payment_api(moyasar_id)

        if status_code == 200:
            # نحدث الداتا في الداتابيز
            try:
                payment = Payment.objects.get(moyasar_id=moyasar_id)
                old_status = payment.status
                payment.status = data.get("status")
                payment.amount = data.get("amount")
                payment.save()

                # إذا تغيرت الحالة إلى paid، نحدث الفاتورة
                if old_status != "paid" and payment.status == "paid":
                    update_invoice_on_payment_success(payment)

            except Payment.DoesNotExist:
                payment = None

            return Response({
                "moyasar_data": data,
                "local_payment": PaymentSerializer(payment).data if payment else None
            })
        else:
            return Response({"error": data}, status=status_code)
    except Exception as e:
        logger.error(f"Error in fetch_payment_view: {str(e)}")
        return Response({"error": str(e)}, status=500)


class ListPaymentsView(APIView):
    """
    API endpoint to list all payments
    """
    def get(self, request):
        try:
            data = list_payments()
            return Response(data)
        except Exception as e:
            logger.error(f"Error in ListPaymentsView: {str(e)}")
            return Response({"error": str(e)}, status=500)


@api_view(["POST"])
def refund_payment_view(request, moyasar_id):
    """
    API endpoint للقيام بالـ refund.
    """
    try:
        amount = request.data.get("amount")
        result = refund_payment(payment_id=moyasar_id, amount=amount)
        
        # تحديث حالة الدفع والفاتورة عند الإرجاع
        try:
            payment = Payment.objects.get(moyasar_id=moyasar_id)
            payment.status = "refunded"
            payment.save()
            logger.info(f"Payment {moyasar_id} status updated to refunded")
        except Payment.DoesNotExist:
            logger.warning(f"Payment {moyasar_id} not found for refund update")
        
        return Response(result)
    except Exception as e:
        logger.error(f"Error in refund_payment_view: {str(e)}")
        return Response({"error": str(e)}, status=500)


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
    try:
        moyasar_id = payment_data.get("id")
        if not moyasar_id:
            logger.error("❌ Payment data missing 'id'")
            return

        payment = Payment.objects.filter(moyasar_id=moyasar_id).select_related('user', 'book').first()
        if not payment:
            logger.warning(f"⚠️ Payment with id {moyasar_id} not found in DB")
            return

        payment.status = "paid"
        payment.paid_at = timezone.now()
        payment.save()

        # ✅ فك القفل عن الكتاب
        unlock_user_book(payment)

    except Exception as e:
        logger.error(f"❌ Error in handle_payment_paid: {str(e)}")


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
@csrf_exempt
def payment_callback_view(request):
    """
    Callback URL لإعادة توجيه المستخدم بعد الدفع
    """
    try:
        status = request.GET.get("status")
        moyasar_id = request.GET.get("id")

        logger.info(f"📞 Callback received - Status: {status}, ID: {moyasar_id}")

        payment = None
        invoice = None

        if moyasar_id:
            try:
                # ✅ جلب بيانات الدفع من Moyasar
                payment_data, status_code = fetch_payment_api(moyasar_id)
                
                if status_code != 200:
                    logger.error(f"❌ Failed to fetch payment from Moyasar: {payment_data}")
                    raise Exception("Could not verify payment")

                logger.info(f"✅ Payment data from Moyasar: {payment_data}")

                # ✅ تحديث أو إنشاء السجل في قاعدة البيانات
                with transaction.atomic():
                    payment, created = Payment.objects.get_or_create(
                        moyasar_id=moyasar_id,
                        defaults={
                            "amount": payment_data.get("amount"),
                            "status": payment_data.get("status"),
                            "description": payment_data.get("description"),
                            "currency": payment_data.get("currency", "SAR"),
                            "source_type": payment_data.get("source", {}).get("type"),
                        }
                    )

                    if not created:
                        # ✅ تحديث الحالة
                        old_status = payment.status
                        payment.status = payment_data.get("status")
                        payment.amount = payment_data.get("amount")
                        payment.save()
                        
                        logger.info(f"✅ Updated payment {moyasar_id}: {old_status} → {payment.status}")

                        # ✅ فك القفل لو الدفع نجح
                        if old_status != "paid" and payment.status == "paid":
                            update_invoice_on_payment_success(payment)
                            unlock_user_book(payment)
                    else:
                        logger.info(f"✅ Created new payment record: {moyasar_id}")

                invoice = getattr(payment, "invoice", None)
                        
            except Payment.DoesNotExist:
                logger.error(f"❌ Payment {moyasar_id} not found in callback")
            except Exception as e:
                logger.error(f"❌ Error processing callback: {e}", exc_info=True)

        return render(request, "payments/payment_success.html", {
            "payment": payment,
            "invoice": invoice,
            "status": status,
        })

    except Exception as e:
        logger.error(f"❌ Critical error in payment_callback_view: {e}", exc_info=True)
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


@csrf_exempt
def unlock_user_book(payment):
    """
    فك قفل الكتاب للمستخدم بعد الدفع الناجح
    """
    try:
        user = payment.user
        book = payment.book

        if not user or not book:
            logger.warning("⚠️ Missing user or book in payment")
            return

        user_book, created = UserBook.objects.update_or_create(
            user=user,
            book=book,
            defaults={
                "status": "unlocked",
                "unlocked_at": timezone.now(),
                "payment": payment
            }
        )

        logger.info(f"✅ User {user.email} unlocked book {book.title} via payment {payment.moyasar_id}")

    except Exception as e:
        logger.error(f"❌ Error unlocking book for payment {payment.moyasar_id}: {str(e)}")
