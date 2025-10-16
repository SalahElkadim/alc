from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import uuid
from datetime import timedelta


# مدير المستخدمين (User Manager)
class CustomUserManager(BaseUserManager):
    def create_user(self, email, full_name, user_type, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        if user_type not in ['admin', 'student']:
            raise ValueError('Invalid user type')

        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, user_type=user_type, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        return self.create_user(email, full_name, password=password, **extra_fields)


# موديل المستخدم المخصص
class CustomUser(AbstractBaseUser, PermissionsMixin):
    USER_TYPES = (
        ('admin', 'Admin'),
        ('student', 'Student'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)  # جديد
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)  # جديد
    failed_login_attempts = models.IntegerField(default=0)  # جديد
    account_locked_until = models.DateTimeField(null=True, blank=True)  # جديد
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'user_type', 'phone']

    def __str__(self):
        return self.email

    def is_account_locked(self):
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False
    
    def allows_multiple_devices(self):
        """تحديد ما إذا كان المستخدم يمكنه الدخول من أجهزة متعددة"""
        return self.user_type == 'admin'

class UserSession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=1024, unique=True)  # JWT token أو session ID
    device_fingerprint = models.CharField(max_length=255)  # بصمة الجهاز
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()  # معلومات المتصفح/التطبيق
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    
    class Meta:
        db_table = 'user_sessions'
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.user.email} - {self.device_fingerprint[:20]}"
