from django.shortcuts import render
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

# انشاء عملية دفع
class CreatePaymentView(APIView):
    def post(self, request):
        user = request.user  # ناخد اليوزر الحالي
        data = request.data
        payment_response = create_payment(
            given_id=request.user.id,
            amount=data.get("amount"),
            description=data.get("description"),
            callback_url=data.get("callback_url"),
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


# نجيب عملية الدفع بالاي دي بتاعها
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

# نعرض كل عمليات الدفع
class ListPaymentsView(APIView):
    """
    API endpoint to list all payments
    """
    def get(self, request):
        data = list_payments()
        return Response(data)

# نعمل ريفند للفلوس
@api_view(["POST"])
def refund_payment_view(request, moyasar_id):
    """
    API endpoint للقيام بالـ refund.
    """
    amount = request.data.get("amount")  # لو فيه refund جزئي
    result = refund_payment(payment_id=moyasar_id, amount=amount)
    return Response(result)



# ميسر يعمل بوست ريكويست يقولنا فيه الدفع تمام 
@api_view(["POST"])
@permission_classes([AllowAny])
def payment_callback_view(request):
    data = request.data

    moyasar_id = data.get("id")
    status = data.get("status")
    amount = data.get("amount")

    if not moyasar_id:
        return Response({"error": "Missing payment ID"}, status=400)

    try:
        payment = Payment.objects.get(moyasar_id=moyasar_id)
        payment.status = status
        payment.amount = amount
        payment.save()

        if status == "paid":
            invoice, created = Invoice.objects.get_or_create(
                payment=payment,
                defaults={
                    "invoice_number": str(uuid.uuid4()),
                    "amount": amount,
                    "currency": getattr(payment, "currency", "SAR"),
                    "description": getattr(payment, "description", ""),
                    "paid_at": timezone.now()
                }
            )

    except Payment.DoesNotExist:
        return Response({"error": "Payment not found"}, status=404)

    return Response({"success": True, "payment": PaymentSerializer(payment).data})

# تفاصيل الفاتورة
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
    
# كل الفواتير
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_invoices_view(request):
    """
    تعرض كل الفواتير الموجودة في النظام
    """
    invoices = Invoice.objects.all().order_by('-created_at')  # ترتيب من الأحدث للأقدم
    serializer = InvoiceSerializer(invoices, many=True)
    return Response(serializer.data)