from rest_framework import serializers
from .models import Payment,Invoice


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            'invoice_number',
            'payment',
            'amount',
            'currency',
            'description',
            'created_at',
            'paid_at'
        ]
        read_only_fields = ['invoice_number', 'created_at', 'paid_at', 'payment']