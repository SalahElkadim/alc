from django.db import models
from users.models import CustomUser
from django.utils import timezone


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('canceled', 'Canceled'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="payments")
    moyasar_id = models.CharField(max_length=100, unique=True)  # id اللي جاي من ميسر
    amount = models.IntegerField()  # المبلغ بالهللة
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="initiated")
    currency = models.CharField(max_length=10, default="SAR")
    description = models.TextField(blank=True, null=True)
    
    # تواريخ مهمة
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    
    # معلومات إضافية من Moyasar
    moyasar_fee = models.IntegerField(blank=True, null=True)  # رسوم ميسر
    source_type = models.CharField(max_length=50, blank=True, null=True)  # نوع مصدر الدفع
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['moyasar_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Payment {self.moyasar_id} - {self.status}"

    @property
    def amount_in_sar(self):
        """المبلغ بالريال السعودي"""
        return self.amount / 100

    def mark_as_paid(self):
        """تحديد الدفعة كمدفوعة"""
        if self.status != 'paid':
            self.status = 'paid'
            self.paid_at = timezone.now()
            self.save()


class Invoice(models.Model):
    INVOICE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('canceled', 'Canceled'),
        ('refunded', 'Refunded'),
    ]
    
    payment = models.OneToOneField(
        'Payment',
        on_delete=models.CASCADE,
        related_name='invoice'
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # المبلغ بالريال
    currency = models.CharField(max_length=10, default='SAR')
    description = models.TextField(blank=True, null=True)
    
    # معلومات العميل (نسخة من بيانات المستخدم وقت إنشاء الفاتورة)
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # التواريخ
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    due_date = models.DateTimeField(blank=True, null=True)
    
    # الحالة
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default='pending')
    
    # معلومات إضافية
    notes = models.TextField(blank=True, null=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # ضريبة القيمة المضافة
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['payment']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.payment.moyasar_id}"

    @property
    def total_amount(self):
        """إجمالي المبلغ مع الضريبة"""
        return self.amount + self.tax_amount

    @property
    def is_paid(self):
        """التحقق من كون الفاتورة مدفوعة"""
        return self.status == 'paid' and self.paid_at is not None

    def mark_as_paid(self):
        """تحديد الفاتورة كمدفوعة"""
        if not self.is_paid:
            self.status = 'paid'
            self.paid_at = timezone.now()
            self.save()

    def save(self, *args, **kwargs):
        # تحديث بيانات العميل من المستخدم المرتبط
        if not self.customer_name and self.payment and self.payment.user:
            user = self.payment.user
            
            # محاولة الحصول على الاسم من عدة مصادر
            if hasattr(user, 'first_name') and hasattr(user, 'last_name'):
                # إذا كان CustomUser يحتوي على first_name و last_name
                self.customer_name = f"{user.first_name} {user.last_name}".strip()
            elif hasattr(user, 'full_name'):
                # إذا كان هناك حقل full_name
                self.customer_name = user.full_name
            elif hasattr(user, 'name'):
                # إذا كان هناك حقل name
                self.customer_name = user.name
            else:
                # الافتراضي هو username
                self.customer_name = user.username
            
            # إذا لم نحصل على اسم، استخدم username
            if not self.customer_name:
                self.customer_name = user.username
                
            # البريد الإلكتروني
            self.customer_email = getattr(user, 'email', '')
            
            # رقم الهاتف إذا كان موجود
            if hasattr(user, 'phone'):
                self.customer_phone = user.phone
            elif hasattr(user, 'phone_number'):
                self.customer_phone = user.phone_number
        
        super().save(*args, **kwargs)