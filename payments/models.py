from django.db import models
from users.models import CustomUser

class Payment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="payments")
    moyasar_id = models.CharField(max_length=100, unique=True)  # id اللي جاي من ميسر
    amount = models.IntegerField()
    status = models.CharField(max_length=20, default="initiated")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.moyasar_id} - {self.status}"


class Invoice(models.Model):
    payment = models.OneToOneField(
        'Payment',
        on_delete=models.CASCADE,
        related_name='invoice'
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='SAR')
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.payment.moyasar_id}"
