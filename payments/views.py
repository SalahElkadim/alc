from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings
from django.utils import timezone
from django.http import Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
import json
import logging
import uuid
from decimal import Decimal

from .models import Payment, Invoice
from .serializers import PaymentSerializer, InvoiceSerializer, InvoiceDetailSerializer
from .moyasar import create_payment, fetch_payment as fetch_payment_api, list_payments, refund_payment
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
        value = request.data.get("value")
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

    # 🔥 NEW: جلب المستخدم من التوكن
    from rest_framework_simplejwt.tokens import AccessToken
    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        from users.models import CustomUser
        user = CustomUser.objects.get(id=user_id)
        logger.info(f"✅ User authenticated: {user.email}")
    except Exception as e:
        logger.error(f"❌ Invalid token: {e}")
        return render(request, "error.html", {"message": "Invalid or expired token"})

    book = None
    if book_id:
        book = Book.objects.filter(id=book_id).first()
        if book:
            amount = int(book.price_sar * 100)
        else:
            return render(request, "error.html", {"message": "Book not found"})

    # 🔥 NEW: إنشاء Payment مبدئي (pending)
    try:
        with transaction.atomic():
            # إنشاء given_id فريد
            given_id = str(uuid.uuid4())
            
            # إنشاء Payment بحالة "pending_form"
            pending_payment = Payment.objects.create(
                moyasar_id=f"PENDING-{given_id}",  # مؤقت
                user=user,
                book=book,
                amount=amount,
                status="pending_form",
                description=f"Unlock book: {book.title}",
                currency="SAR",
            )
            
            logger.info(f"✅ Created pending payment: {pending_payment.id}")
            
            # حفظ given_id في session أو نُرسله للـ HTML
            payment_session_id = str(pending_payment.id)
            
    except Exception as e:
        logger.error(f"❌ Failed to create pending payment: {e}")
        return render(request, "error.html", {"message": "Failed to initialize payment"})

    return render(request, "payment.html", {
        "publishable_key": settings.MOYASAR_PUBLISHABLE_KEY,
        "amount": amount,
        "access_token": token,
        'book_id': book_id,
        'book': book,
        'payment_session_id': payment_session_id,  # 🔥 NEW
        'user_email': user.email,  # 🔥 NEW
    })


class CreatePaymentView(APIView):
    """
    إنشاء عملية دفع جديدة لكتاب محدد باستخدام Tokenization (ميسر)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            user = request.user

            # 🔍 DEBUG: طباعة المستخدم
            logger.info(f"🔍 DEBUG: User={user.email}, ID={user.id}")

            # 1️⃣ التحقق من البيانات
            token = data.get("source", {}).get("token")
            book_id = data.get("book_id")

            if not token:
                return Response({"success": False, "error": "Token is required"}, status=400)

            if not book_id:
                return Response({"success": False, "error": "book_id is required"}, status=400)

            # 2️⃣ جلب الكتاب
            try:
                book = Book.objects.get(id=book_id)
            except Book.DoesNotExist:
                return Response({"success": False, "error": "Book not found"}, status=404)

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
                    "given_id": given_id,
                }
            )

            logger.info(f"📩 Moyasar Response Status: {status_code}")
            logger.info(f"📩 Moyasar Response Body: {payment_response}")
            
            # 🔍 DEBUG: طباعة كل شيء
            print(f"\n{'='*60}")
            print(f"🔍 MOYASAR RESPONSE DEBUG")
            print(f"{'='*60}")
            print(f"Status Code: {status_code}")
            print(f"Response: {json.dumps(payment_response, indent=2)}")
            print(f"User: {user.email}")
            print(f"Book ID: {book_id}")
            print(f"{'='*60}\n")

            # ✅ التحقق من نجاح الطلب
            if status_code not in [200, 201]:
                logger.error(f"❌ Moyasar API Error: {payment_response}")
                return Response({
                    "success": False,
                    "error": payment_response.get("message", "Failed to create payment"),
                    "moyasar_error": payment_response
                }, status=status_code)

            # 6️⃣ التحقق من وجود ID في الـ response
            if "id" not in payment_response:
                logger.error(f"❌ No 'id' in Moyasar response: {payment_response}")
                return Response({
                    "success": False,
                    "error": "Invalid response from payment gateway"
                }, status=500)

            moyasar_id = payment_response["id"]

            # 7️⃣ حفظ الدفع في قاعدة البيانات
            with transaction.atomic():
                # 🔍 DEBUG: قبل الحفظ
                print(f"\n🔍 BEFORE SAVE:")
                print(f"User: {user.email} (ID: {user.id})")
                print(f"Book: {book.title} (ID: {book.id})")
                print(f"Moyasar ID: {moyasar_id}")
                print(f"Amount: {amount_halalah}")
                
                payment, created = Payment.objects.get_or_create(
                    moyasar_id=moyasar_id,
                    defaults={
                        "user": user,
                        "book": book,
                        "amount": amount_halalah,
                        "status": payment_response.get("status", "initiated"),
                        "description": description,
                        "currency": "SAR",
                        "source_type": payment_response.get("source", {}).get("type", "token"),
                    }
                )
                
                # 🔍 DEBUG: بعد الحفظ
                print(f"\n🔍 AFTER SAVE:")
                print(f"Payment Created: {created}")
                print(f"Payment ID in DB: {payment.id if payment else 'None'}")
                print(f"Payment Status: {payment.status if payment else 'None'}")
                print(f"Payment User: {payment.user.email if payment and payment.user else 'None'}")
                print(f"Payment Book: {payment.book.title if payment and payment.book else 'None'}")
                print(f"{'='*60}\n")

                if not created:
                    payment.status = payment_response.get("status", payment.status)
                    payment.amount = amount_halalah
                    payment.book = book
                    payment.user = user
                    payment.save()
                    logger.warning(f"⚠️ Payment {moyasar_id} already exists, updated")

                # 8️⃣ إنشاء الفاتورة (FIXED)
                try:
                    self.create_invoice(payment, description)
                    logger.info(f"✅ Invoice created for payment {moyasar_id}")
                except Exception as e:
                    logger.error(f"⚠️ Failed to create invoice: {e}", exc_info=True)
                    # نكمل العملية حتى لو فشل إنشاء الفاتورة

                logger.info(f"✅ Payment saved: {moyasar_id} - Status: {payment.status}")

            # 9️⃣ معالجة الحالة
            status = payment_response.get("status")
            moyasar_source = payment_response.get("source", {})

            if status == "initiated":
                transaction_url = moyasar_source.get("transaction_url")
                if not transaction_url:
                    logger.error(f"❌ No transaction_url in response: {payment_response}")
                    return Response({
                        "success": False,
                        "error": "No transaction URL provided"
                    }, status=500)

                return Response({
                    "status": "initiated",
                    "transaction_url": transaction_url,
                    "payment_id": moyasar_id,
                    "book": {"id": str(book.id), "title": book.title},
                })

            elif status == "paid":
                # 🔥 FIX: استخدام الدالة المحسّنة
                unlock_success = unlock_user_book(payment)
                if unlock_success:
                    return Response({
                        "status": "paid",
                        "message": "Book unlocked successfully",
                        "payment_id": moyasar_id,
                        "book": {"id": str(book.id), "title": book.title},
                    })
                else:
                    return Response({
                        "status": "paid",
                        "message": "Payment successful but unlock failed",
                        "payment_id": moyasar_id,
                    }, status=500)

            else:
                return Response({
                    "status": status,
                    "message": payment_response.get("message", "Unknown status"),
                    "payment_id": moyasar_id,
                }, status=400)

        except Exception as e:
            logger.error(f"❌ Error in CreatePaymentView: {e}", exc_info=True)
            return Response({
                "success": False,
                "error": str(e)
            }, status=500)

    def create_invoice(self, payment, description):
        """إنشاء فاتورة مرتبطة بالدفع"""
        try:
            invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            Invoice.objects.get_or_create(
                payment=payment,
                defaults={
                    "invoice_number": invoice_number,
                    "amount": Decimal(payment.amount) / 100,
                    "currency": "SAR",
                    "description": description,
                }
            )
            logger.info(f"✅ Invoice created for payment {payment.moyasar_id}")
        except Exception as e:
            logger.error(f"❌ Error creating invoice: {e}", exc_info=True)
            raise  # نرفع الـ exception للتعامل معها في المستوى الأعلى


@api_view(["GET"])
def fetch_payment_view(request, moyasar_id):
    try:
        data, status_code = fetch_payment_api(moyasar_id)

        if status_code == 200:
            try:
                payment = Payment.objects.get(moyasar_id=moyasar_id)
                old_status = payment.status
                payment.status = data.get("status")
                payment.amount = data.get("amount")
                payment.save()

                # 🔥 FIX: تحديث الفاتورة بشكل آمن
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
    try:
        amount = request.data.get("amount")
        result = refund_payment(payment_id=moyasar_id, amount=amount)
        
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
        # 🔍 DEBUG: طباعة كل البيانات الواردة
        print(f"\n{'='*60}")
        print(f"🔔 WEBHOOK RECEIVED!")
        print(f"{'='*60}")
        print(f"Headers: {dict(request.headers)}")
        print(f"Body: {request.body.decode('utf-8')}")
        print(f"{'='*60}\n")
        
        signature = request.headers.get('X-Moyasar-Signature')
        if not verify_webhook_signature(request.body, signature):
            logger.warning("Invalid webhook signature")

        payload = json.loads(request.body)
        event_type = payload.get('type')
        payment_data = payload.get('data', {})
        
        logger.info(f"📞 Webhook: {event_type} for payment {payment_data.get('id')}")
        print(f"🔍 Event Type: {event_type}")
        print(f"🔍 Payment Data: {json.dumps(payment_data, indent=2)}")

        if event_type == 'payment_paid':
            handle_payment_paid(payment_data)
        elif event_type == 'payment_failed':
            handle_payment_failed(payment_data)
        elif event_type == 'payment_refunded':
            handle_payment_refunded(payment_data)

        return HttpResponse("OK", status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        print(f"❌ WEBHOOK ERROR: {str(e)}")
        return HttpResponse("Error", status=200)


def verify_webhook_signature(payload, signature):
    try:
        if not signature or not hasattr(settings, 'MOYASAR_WEBHOOK_SECRET'):
            return True
        
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
        return True


def unlock_user_book(payment):
    """
    🔥 FIXED: فك قفل الكتاب للمستخدم بعد الدفع الناجح
    Returns: True إذا نجحت العملية، False إذا فشلت
    """
    try:
        user = payment.user
        book = payment.book

        # ✅ التحقق من وجود المستخدم والكتاب
        if not user:
            logger.error(f"❌ Payment {payment.moyasar_id} has no user!")
            return False
            
        if not book:
            logger.error(f"❌ Payment {payment.moyasar_id} has no book!")
            return False

        # ✅ استخدام transaction للتأكد من سلامة البيانات
        with transaction.atomic():
            user_book, created = UserBook.objects.update_or_create(
                user=user,
                book=book,
                defaults={
                    "status": "unlocked",
                    "unlocked_at": timezone.now(),
                    "payment": payment
                }
            )

            if created:
                logger.info(f"✅ NEW: User {user.email} unlocked {book.title}")
            else:
                logger.info(f"✅ UPDATED: User {user.email} unlocked {book.title}")

        return True

    except Exception as e:
        logger.error(f"❌ Critical error unlocking book for payment {payment.moyasar_id}: {str(e)}", exc_info=True)
        return False


def handle_payment_paid(payment_data):
    """
    🔥 FIXED: معالجة webhook للدفع الناجح
    """
    try:
        moyasar_id = payment_data.get("id")
        if not moyasar_id:
            logger.error("❌ Payment data missing 'id'")
            return

        logger.info(f"🔔 Webhook: payment_paid for {moyasar_id}")

        # ✅ جلب البيانات من metadata (FIXED: معالجة None)
        metadata = payment_data.get("metadata") or {}
        user_id = metadata.get("user_id")
        book_id = metadata.get("book_id")
        
        # 🔍 DEBUG: طباعة metadata
        print(f"\n🔍 WEBHOOK METADATA DEBUG:")
        print(f"Payment Data Keys: {list(payment_data.keys())}")
        print(f"Metadata Type: {type(metadata)}")
        print(f"Metadata Content: {metadata}")
        print(f"User ID: {user_id}")
        print(f"Book ID: {book_id}")
        print(f"{'='*60}\n")

        user = None
        book = None

        # ✅ جلب المستخدم
        if user_id:
            try:
                from users.models import CustomUser
                user = CustomUser.objects.get(id=user_id)
                logger.info(f"✅ Found user: {user.email}")
            except Exception as e:
                logger.warning(f"⚠️ User {user_id} not found: {e}")
        else:
            logger.warning(f"⚠️ No user_id in metadata!")

        # ✅ جلب الكتاب
        if book_id:
            try:
                book = Book.objects.get(id=book_id)
                logger.info(f"✅ Found book: {book.title}")
            except Exception as e:
                logger.warning(f"⚠️ Book {book_id} not found: {e}")
        else:
            logger.warning(f"⚠️ No book_id in metadata!")
            
        # 🔥 NEW: إذا لم نجد user/book في metadata، حاول البحث في Payment الموجود
        if not user or not book:
            logger.info(f"🔍 Trying to find user/book from existing payment...")
            
            # 🔥 NEW: محاولة استخراج session_id من callback_url
            callback_url = payment_data.get('callback_url', '')
            session_id = None
            
            if 'session_id=' in callback_url:
                try:
                    session_id = callback_url.split('session_id=')[1].split('&')[0]
                    logger.info(f"✅ Extracted session_id from callback_url: {session_id}")
                except:
                    logger.warning(f"⚠️ Failed to extract session_id from: {callback_url}")
            
            # محاولة جلب Payment الموجود
            existing_payment = None
            
            # أولاً: محاولة بـ session_id
            if session_id:
                try:
                    existing_payment = Payment.objects.get(id=session_id, status="pending_form")
                    logger.info(f"✅ Found pending payment by session_id: {session_id}")
                except Payment.DoesNotExist:
                    logger.warning(f"⚠️ No pending payment with session_id: {session_id}")
            
            # ثانياً: محاولة بـ moyasar_id
            if not existing_payment:
                existing_payment = Payment.objects.filter(moyasar_id=moyasar_id).first()
                if existing_payment:
                    logger.info(f"✅ Found existing payment by moyasar_id")
            
            # استخراج user و book
            if existing_payment:
                if not user and existing_payment.user:
                    user = existing_payment.user
                    logger.info(f"✅ Found user from existing payment: {user.email}")
                if not book and existing_payment.book:
                    book = existing_payment.book
                    logger.info(f"✅ Found book from existing payment: {book.title}")
            
            # 🔥 NEW: محاولة استخراج email من description
            if not user:
                description = payment_data.get('description', '')
                logger.info(f"🔍 Trying to extract email from description: {description}")
                
                # البحث عن email في الوصف
                import re
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', description)
                if email_match:
                    email = email_match.group(0)
                    try:
                        from users.models import CustomUser
                        user = CustomUser.objects.get(email=email)
                        logger.info(f"✅ Found user from description: {user.email}")
                    except CustomUser.DoesNotExist:
                        logger.warning(f"⚠️ User with email {email} not found")

        with transaction.atomic():
            # ✅ محاولة جلب الدفع أولاً
            payment = Payment.objects.filter(moyasar_id=moyasar_id).first()

            if payment:
                # ✅ تحديث الدفع الموجود
                logger.info(f"✅ Payment {moyasar_id} already exists, updating...")
                payment.status = "paid"
                payment.paid_at = timezone.now()
                
                # ✅ تحديث user و book لو مش موجودين
                if not payment.user and user:
                    payment.user = user
                    logger.info(f"✅ Added user to existing payment: {user.email}")
                if not payment.book and book:
                    payment.book = book
                    logger.info(f"✅ Added book to existing payment: {book.title}")
                    
                payment.save()
                logger.info(f"✅ Updated existing payment {moyasar_id}")
            else:
                # ✅ إنشاء دفع جديد
                try:
                    payment = Payment.objects.create(
                        moyasar_id=moyasar_id,
                        user=user,
                        book=book,
                        amount=payment_data.get("amount"),
                        status="paid",
                        paid_at=timezone.now(),
                        description=payment_data.get("description"),
                        currency=payment_data.get("currency", "SAR"),
                        source_type=payment_data.get("source", {}).get("type"),
                    )
                    logger.info(f"✅ Created new payment {moyasar_id} via webhook")
                except Exception as e:
                    # 🔥 FIX: إذا حصل duplicate key (race condition)
                    if 'duplicate key' in str(e).lower():
                        logger.warning(f"⚠️ Race condition detected, fetching existing payment")
                        payment = Payment.objects.get(moyasar_id=moyasar_id)
                        
                        # تحديث البيانات
                        payment.status = "paid"
                        payment.paid_at = timezone.now()
                        if not payment.user and user:
                            payment.user = user
                        if not payment.book and book:
                            payment.book = book
                        payment.save()
                    else:
                        raise

            # 🔥 FIX: فك القفل وتحديث الفاتورة
            if payment.user and payment.book:
                unlock_success = unlock_user_book(payment)
                if unlock_success:
                    logger.info(f"✅ Book unlocked successfully for {moyasar_id}")
                else:
                    logger.error(f"❌ Failed to unlock book for {moyasar_id}")
                
                # ✅ تحديث الفاتورة (آمن)
                update_invoice_on_payment_success(payment)
            else:
                logger.warning(f"⚠️ Cannot unlock - missing user or book for {moyasar_id}")

    except Exception as e:
        logger.error(f"❌ Error in handle_payment_paid: {str(e)}", exc_info=True)


def handle_payment_failed(payment_data):
    moyasar_id = payment_data.get('id')
    
    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        payment.status = 'failed'
        payment.save()
        logger.info(f"Payment {moyasar_id} marked as failed")
        
    except Payment.DoesNotExist:
        logger.warning(f"Payment {moyasar_id} not found")
    except Exception as e:
        logger.error(f"Error handling payment_failed: {str(e)}")


def handle_payment_refunded(payment_data):
    moyasar_id = payment_data.get('id')
    
    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        payment.status = 'refunded'
        payment.save()
        logger.info(f"Payment {moyasar_id} marked as refunded")
        
    except Payment.DoesNotExist:
        logger.warning(f"Payment {moyasar_id} not found")
    except Exception as e:
        logger.error(f"Error handling payment_refunded: {str(e)}")


def update_invoice_on_payment_success(payment):
    """
    🔥 FIXED: تحديث الفاتورة عند نجاح الدفع (معالجة آمنة)
    """
    try:
        # ✅ التحقق من وجود الفاتورة أولاً
        if not hasattr(payment, 'invoice'):
            logger.warning(f"⚠️ No invoice exists for payment {payment.moyasar_id}")
            return
        
        invoice = payment.invoice
        
        # ✅ التحقق من أن الفاتورة لم تكن مدفوعة مسبقاً
        if not invoice.paid_at:
            invoice.paid_at = timezone.now()
            invoice.status = 'paid'
            invoice.save()
            logger.info(f"✅ Invoice {invoice.invoice_number} marked as paid")
        else:
            logger.info(f"ℹ️ Invoice {invoice.invoice_number} was already paid")
            
    except Invoice.DoesNotExist:
        logger.warning(f"⚠️ No invoice found for payment {payment.moyasar_id}")
    except Exception as e:
        logger.error(f"❌ Error updating invoice for payment {payment.moyasar_id}: {str(e)}", exc_info=True)


@csrf_exempt
def payment_callback_view(request):
    """
    🔥 FIXED: Callback URL لإعادة توجيه المستخدم بعد الدفع
    """
    try:
        # 🔍 DEBUG: طباعة كل البيانات
        print(f"\n{'='*60}")
        print(f"🔔 CALLBACK RECEIVED!")
        print(f"{'='*60}")
        print(f"GET Params: {dict(request.GET)}")
        print(f"Headers: {dict(request.headers)}")
        print(f"{'='*60}\n")
        
        status = request.GET.get("status")
        moyasar_id = request.GET.get("id")
        payment_session_id = request.GET.get("session_id")  # 🔥 NEW

        logger.info(f"📞 Callback - Status: {status}, Moyasar ID: {moyasar_id}, Session: {payment_session_id}")

        payment = None
        invoice = None

        if moyasar_id:
            try:
                # 🔥 NEW: أولاً نحاول إيجاد Payment بـ session_id
                if payment_session_id:
                    try:
                        pending_payment = Payment.objects.get(id=payment_session_id, status="pending_form")
                        logger.info(f"✅ Found pending payment: {pending_payment.id}")
                        
                        # 🔥 FIX: تحقق إذا كان moyasar_id موجود بالفعل (من Webhook)
                        existing_payment_with_moyasar = Payment.objects.filter(moyasar_id=moyasar_id).first()
                        
                        if existing_payment_with_moyasar:
                            # ✅ Webhook سبقنا وحفظ Payment
                            logger.info(f"⚠️ Payment {moyasar_id} already exists (from webhook)")
                            
                            # نحذف الـ pending payment ونستخدم الموجود
                            pending_payment.delete()
                            payment = existing_payment_with_moyasar
                            
                            # نتأكد من وجود user و book
                            if not payment.user or not payment.book:
                                # نحاول نحصل عليهم من الـ pending
                                if not payment.user:
                                    # نجلب من Moyasar description
                                    payment_data, _ = fetch_payment_api(moyasar_id)
                                    description = payment_data.get('description', '')
                                    if 'sada@gmail.com' in description:  # مثال
                                        from users.models import CustomUser
                                        try:
                                            email = description.split(' - ')[-1]
                                            user = CustomUser.objects.get(email=email)
                                            payment.user = user
                                            logger.info(f"✅ Found user from description: {user.email}")
                                        except:
                                            pass
                                
                                payment.save()
                            
                            logger.info(f"✅ Using webhook-created payment")
                        else:
                            # ✅ Webhook لم يصل بعد، نحدث الـ pending
                            pending_payment.moyasar_id = moyasar_id
                            pending_payment.status = "initiated"
                            pending_payment.save()
                            
                            payment = pending_payment
                            logger.info(f"✅ Updated pending payment with moyasar_id: {moyasar_id}")
                        
                    except Payment.DoesNotExist:
                        logger.warning(f"⚠️ Pending payment {payment_session_id} not found")
                    except Exception as e:
                        logger.error(f"❌ Error handling pending payment: {e}", exc_info=True)
                
                # إذا لم نجد payment بالـ session_id، نجلب من Moyasar
                if not payment:
                    # ✅ جلب بيانات الدفع من Moyasar
                    payment_data, status_code = fetch_payment_api(moyasar_id)
                    
                    if status_code != 200:
                        logger.error(f"❌ Failed to fetch from Moyasar: {payment_data}")
                        raise Exception("Could not verify payment")

                    logger.info(f"✅ Payment data from Moyasar: {json.dumps(payment_data, indent=2)}")

                    # ✅ استخراج البيانات من metadata (FIXED: معالجة None)
                    metadata = payment_data.get("metadata") or {}
                    user_id = metadata.get("user_id")
                    book_id = metadata.get("book_id")
                    
                    # 🔍 DEBUG: طباعة metadata
                    print(f"\n🔍 CALLBACK METADATA DEBUG:")
                    print(f"Payment Data Keys: {list(payment_data.keys())}")
                    print(f"Metadata Type: {type(metadata)}")
                    print(f"Metadata Content: {metadata}")
                    print(f"User ID: {user_id}")
                    print(f"Book ID: {book_id}")
                    print(f"{'='*60}\n")

                    # ✅ جلب الـ user والـ book
                    user = None
                    book = None

                    if user_id:
                        try:
                            from users.models import CustomUser
                            user = CustomUser.objects.get(id=user_id)
                            logger.info(f"✅ Found user from metadata: {user.email}")
                        except Exception as e:
                            logger.warning(f"⚠️ Could not find user {user_id}: {e}")
                    else:
                        logger.warning(f"⚠️ No user_id in metadata!")

                    if book_id:
                        try:
                            book = Book.objects.get(id=book_id)
                            logger.info(f"✅ Found book from metadata: {book.title}")
                        except Exception as e:
                            logger.warning(f"⚠️ Could not find book {book_id}: {e}")
                    else:
                        logger.warning(f"⚠️ No book_id in metadata!")
                        
                    # 🔥 NEW: إذا لم نجد user/book في metadata، حاول البحث في Payment الموجود
                    if not user or not book:
                        logger.info(f"🔍 Trying to find user/book from existing payment...")
                        existing_payment = Payment.objects.filter(moyasar_id=moyasar_id).first()
                        if existing_payment:
                            if not user and existing_payment.user:
                                user = existing_payment.user
                                logger.info(f"✅ Found user from existing payment: {user.email}")
                            if not book and existing_payment.book:
                                book = existing_payment.book
                                logger.info(f"✅ Found book from existing payment: {book.title}")

                    # ✅ حفظ أو تحديث الدفع
                    with transaction.atomic():
                        # 🔍 DEBUG: قبل الحفظ في Callback
                        print(f"\n🔍 CALLBACK - BEFORE SAVE:")
                        print(f"Moyasar ID: {moyasar_id}")
                        print(f"User: {user.email if user else 'None'} (ID: {user.id if user else 'None'})")
                        print(f"Book: {book.title if book else 'None'} (ID: {book.id if book else 'None'})")
                        print(f"Status: {payment_data.get('status')}")
                        
                        payment, created = Payment.objects.get_or_create(
                            moyasar_id=moyasar_id,
                            defaults={
                                "user": user,
                                "book": book,
                                "amount": payment_data.get("amount"),
                                "status": payment_data.get("status"),
                                "description": payment_data.get("description"),
                                "currency": payment_data.get("currency", "SAR"),
                                "source_type": payment_data.get("source", {}).get("type"),
                            }
                        )
                        
                        # 🔍 DEBUG: بعد الحفظ
                        print(f"\n🔍 CALLBACK - AFTER SAVE:")
                        print(f"Payment Created: {created}")
                        print(f"Payment ID in DB: {payment.id if payment else 'None'}")
                        print(f"Payment Status: {payment.status if payment else 'None'}")

                        if not created:
                            # ✅ تحديث البيانات
                            old_status = payment.status
                            payment.status = payment_data.get("status")
                            payment.amount = payment_data.get("amount")
                            
                            # ✅ تحديث user و book لو مش موجودين
                            if not payment.user and user:
                                payment.user = user
                            if not payment.book and book:
                                payment.book = book
                                
                            payment.save()
                            
                            logger.info(f"✅ Updated: {old_status} → {payment.status}")

                            # 🔥 FIX: فك القفل لو الدفع نجح
                            if old_status != "paid" and payment.status == "paid":
                                if payment.user and payment.book:
                                    unlock_success = unlock_user_book(payment)
                                    if unlock_success:
                                        update_invoice_on_payment_success(payment)
                                else:
                                    logger.warning(f"⚠️ Cannot unlock book - missing user or book")
                        else:
                            logger.info(f"✅ Created payment: {moyasar_id}")
                            
                            # 🔥 FIX: فك القفل لو الدفع جاهز
                            if payment.status == "paid" and payment.user and payment.book:
                                unlock_success = unlock_user_book(payment)
                                if unlock_success:
                                    update_invoice_on_payment_success(payment)
                
                # 🔥 NEW: فك القفل للـ payment الموجود
                if payment and payment.status == "paid":
                    if payment.user and payment.book:
                        unlock_success = unlock_user_book(payment)
                        if unlock_success:
                            update_invoice_on_payment_success(payment)
                            logger.info(f"✅ Book unlocked in callback for {moyasar_id}")

                # ✅ جلب الفاتورة بشكل آمن
                invoice = getattr(payment, "invoice", None)
                        
            except Exception as e:
                logger.error(f"❌ Error in callback: {e}", exc_info=True)

        return render(request, "payments/payment_success.html", {
            "payment": payment,
            "invoice": invoice,
            "status": status,
        })

    except Exception as e:
        logger.error(f"❌ Critical error in callback: {e}", exc_info=True)
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


@csrf_exempt
def test_callback_view(request):
    return HttpResponse("Callback test successful", status=200)