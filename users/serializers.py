from rest_framework import serializers
from .models import CustomUser, UserSession
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .utils import generate_device_fingerprint, get_client_ip
from django.utils import timezone


from rest_framework import serializers
from .models import CustomUser
from rest_framework_simplejwt.tokens import RefreshToken

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = CustomUser
        fields = ['email', 'full_name', 'phone', 'user_type', 'password', 'is_staff']
        extra_kwargs = {
            'email': {'validators': []},  # إزالة الـ validators من الـ email field
        }

    def validate(self, attrs):
        email = attrs.get('email')
        if CustomUser.objects.filter(email=email).exists():
            error = serializers.ValidationError({})
            error.detail = {"error_message": "البريد الإلكتروني مسجل بالفعل"}
            raise error
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def to_representation(self, instance):
        tokens = RefreshToken.for_user(instance)
        return {
            "user": {
                "id": instance.id,
                "email": instance.email,
                "full_name": instance.full_name,
                "phone": instance.phone,
                "user_type": instance.user_type,
                "is_staff":instance.is_staff
            },
            "tokens": {
                "refresh": str(tokens),
                "access": str(tokens.access_token),
            }
        }

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        request = self.context.get('request')

        if request is None:
            raise serializers.ValidationError({"error_message": "Request context is not available."})

        email = data.get("email")
        password = data.get("password")

        user = authenticate(email=email, password=password)

        if user is None:
            raise serializers.ValidationError({"error_message": "Invalid email or password."})
        if not user.is_active:
            raise serializers.ValidationError({"error_message": "User is deactivated."})

        tokens = RefreshToken.for_user(user)

        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "user_type": user.user_type,
                "allows_multiple_devices": user.allows_multiple_devices(),
                "is_staff":user.is_staff
            },
            "tokens": {
                "refresh": str(tokens),
                "access": str(tokens.access_token),
            }
        }


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError({"error_message": "Current password is incorrect."})
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError({"error_message": " ".join(e.messages)})
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"error_message": "Passwords don't match."})
        return data


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'full_name', 'phone', 'user_type', 'is_email_verified', 'date_joined','payment_status']
        read_only_fields = ['id', 'email', 'user_type', 'date_joined','payment_status']


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

