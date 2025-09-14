from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from .moyasar import create_payment
import requests
from rest_framework.decorators import api_view
from django.conf import settings
from .models import Payment,Invoice
from .serializers import PaymentSerializer,InvoiceSerializer
from .moyasar import fetch_payment as fetch_payment_api
from .moyasar import list_payments,refund_payment
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny,IsAuthenticated
import uuid
from django.utils import timezone
from django.http import Http404


class CreatePaymentView(APIView):
    def post(self, request):
        user = request.user  # ناخد اليوزر الحالي
        data = request.data

        source_data = data.get("source", {})  # هنسحب كل البيانات من source
        source = {
            "type": source_data.get("type"),
            "name": source_data.get("name"),
            "number": source_data.get("number"),
            "month": source_data.get("month"),
            "year": source_data.get("year"),
            "cvc": source_data.get("cvc"),
            "3ds": True,
            "manual": False,
            "save_card": False
        }

        payment_response = create_payment(
            given_id=request.user.id,
            amount=data.get("amount"),
            description=data.get("description"),
            #callback_url=data.get("callback_url"),
            source=source,
            metadata=data.get("metadata")
        )

        # نخزن الدفع في الداتابيز لو اتنجحت العملية
        if "id" in payment_response:
            payment, created = Payment.objects.get_or_create(
                user=user,
                moyasar_id=payment_response.get("id"),
                defaults={
                    "amount": payment_response.get("amount"),
                    "status": payment_response.get("status"),        
                }
            )

        return Response({
            "moyasar_data": payment_response,
        })



@api_view(["GET"])
def fetch_payment_view(request, moyasar_id):
    data, status_code = fetch_payment_api(moyasar_id)

    if status_code == 200:
        # نحدث الداتا في الداتابيز
        try:
            payment = Payment.objects.get(moyasar_id=moyasar_id)
            payment.status = data.get("status")
            payment.amount = data.get("amount")
            payment.save()
        except Payment.DoesNotExist:
            payment = None

        return Response({
            "moyasar_data": data,
            "local_payment": PaymentSerializer(payment).data if payment else None
        })
    else:
        return Response({"error": data}, status=status_code)
    
class ListPaymentsView(APIView):
    """
    API endpoint to list all payments
    """
    def get(self, request):
        data = list_payments()
        return Response(data)

@api_view(["POST"])
def refund_payment_view(request, moyasar_id):
    """
    API endpoint للقيام بالـ refund.
    """
    amount = request.data.get("amount")  # لو فيه refund جزئي
    result = refund_payment(payment_id=moyasar_id, amount=amount)
    return Response(result)



from django.shortcuts import render
@api_view(["POST"])
@permission_classes([AllowAny])
def payment_callback_view(request):
    print("📩 Callback received")
    print("Headers:", dict(request.headers))
    print("Body:", request.data)

    data = request.data

    moyasar_id = data.get("id")
    status = data.get("status")
    amount = data.get("amount")
    currency = data.get("currency")

    if not moyasar_id:
        return Response({"error": "Missing payment ID"}, status=400)

    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)

        # تأكد أن المبلغ متطابق
        if payment.amount != amount:
            return Response({"error": "Amount mismatch"}, status=400)

        # تحديث بيانات الدفع
        payment.status = status
        payment.amount = amount
        payment.currency = currency or payment.currency
        payment.save()

        # لو الدفع ناجح → إنشاء فاتورة
        if status == "paid":
            invoice, created = Invoice.objects.get_or_create(
                payment=payment,
                defaults={
                    "invoice_number": str(uuid.uuid4()),
                    "amount": amount,
                    "currency": currency or "SAR",
                    "description": payment.description,
                    "paid_at": timezone.now(),
                }
            )

    except Payment.DoesNotExist:
        return Response({"error": "Payment not found"}, status=404)

    # الكولباك يرد على البوابة فقط
    return Response({"success": True})

@permission_classes([AllowAny])
def payment_redirect_view(request):
    status = request.GET.get("status")
    moyasar_id = request.GET.get("id")

    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        invoice = getattr(payment, "invoice", None)
    except Payment.DoesNotExist:
        payment = None
        invoice = None

    if status == "paid" and payment:
        return render(request, "payments/payment_success.html", {
            "payment": payment,
            "invoice": invoice,
        })
    else:
        return render(request, "payments/payment_failed.html", {
            "payment": payment,
        })




@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_detail_view(request, moyasar_id):
    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        invoice = payment.invoice  # لأننا عملنا OneToOneField
        serializer = InvoiceSerializer(invoice)
        return Response(serializer.data)
    except Payment.DoesNotExist:
        return Response({"error": "Payment not found"}, status=404)
    except Invoice.DoesNotExist:
        return Response({"error": "Invoice not found"}, status=404)
    

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_invoices_view(request):
    """
    تعرض كل الفواتير الموجودة في النظام
    """
    invoices = Invoice.objects.all().order_by('-created_at')  # ترتيب من الأحدث للأقدم
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)


