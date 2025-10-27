from rest_framework import serializers
from .models import Payment, Invoice


class PaymentSerializer(serializers.ModelSerializer):
    amount_in_sar = serializers.ReadOnlyField()
    user_name = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'moyasar_id',
            'user',
            'user_name',
            'amount',
            'amount_in_sar',
            'status',
            'currency',
            'description',
            'moyasar_fee',
            'source_type',
            'created_at',
            'updated_at',
            'paid_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'paid_at', 
            'amount_in_sar', 'user_name'
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    payment_moyasar_id = serializers.CharField(source='payment.moyasar_id', read_only=True)
    total_amount = serializers.ReadOnlyField()
    is_paid = serializers.ReadOnlyField()
    
    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'payment',
            'payment_moyasar_id',
            'payment_status',
            'amount',
            'total_amount',
            'currency',
            'description',
            'customer_name',
            'customer_email',
            'customer_phone',
            'status',
            'is_paid',
            'tax_amount',
            'notes',
            'created_at',
            'paid_at',
            'due_date'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'created_at', 'paid_at',
            'payment_status', 'payment_moyasar_id', 'total_amount', 'is_paid'
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """
    Serializer مفصل للفواتير مع معلومات الدفع
    """
    payment = PaymentSerializer(read_only=True)
    total_amount = serializers.ReadOnlyField()
    is_paid = serializers.ReadOnlyField()
    
    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'payment',
            'amount',
            'total_amount',
            'currency',
            'description',
            'customer_name',
            'customer_email',
            'customer_phone',
            'status',
            'is_paid',
            'tax_amount',
            'notes',
            'created_at',
            'paid_at',
            'due_date'
        ]