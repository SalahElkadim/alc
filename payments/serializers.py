from rest_framework import serializers
from .models import Payment

class CreatePaymentSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=100)  # أقل مبلغ 1 ريال
    description = serializers.CharField(max_length=500)
    customer_name = serializers.CharField(max_length=100, required=False)
    customer_email = serializers.EmailField(required=False)
    customer_phone = serializers.CharField(max_length=20, required=False)
    
    def validate_amount(self, value):
        if value < 100:  # أقل من ريال واحد
            raise serializers.ValidationError("المبلغ يجب أن يكون على الأقل 1 ريال (100 هللة)")
        return value

class PaymentStatusSerializer(serializers.ModelSerializer):
    amount_in_riyals = serializers.ReadOnlyField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'moyasar_payment_id', 'amount', 'amount_in_riyals',
            'currency', 'description', 'status', 'customer_name',
            'customer_email', 'customer_phone', 'created_at', 'paid_at'
        ]