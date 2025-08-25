from django.db import models
from users.models import CustomUser

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'في الانتظار'),
        ('initiated', 'تم الإنشاء'),
        ('paid', 'مدفوع'),
        ('failed', 'فشل'),
        ('refunded', 'مسترد'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    moyasar_payment_id = models.CharField(max_length=100, unique=True)
    amount = models.IntegerField()  # بالهللة
    currency = models.CharField(max_length=3, default='SAR')
    description = models.TextField()
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # بيانات إضافية
    customer_name = models.CharField(max_length=100, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # التواريخ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # URLs
    success_url = models.URLField(blank=True)
    failure_url = models.URLField(blank=True)
    
    def __str__(self):
        return f"Payment {self.moyasar_payment_id} - {self.status}"
    
    @property
    def amount_in_riyals(self):
        return self.amount / 100