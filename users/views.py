from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .serializers import RegisterSerializer, LoginSerializer, ProfileSerializer, ForgotPasswordSerializer, ChangePasswordSerializer
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging
from .models import CustomUser,UserSession
from .utils import generate_device_fingerprint
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode,urlsafe_base64_decode
from django.utils.encoding import force_bytes,force_str





class RegisterView(APIView):
    permission_classes = []  
    authentication_classes = [] 
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(serializer.to_representation(user), status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class LoginView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        # فحص IP والحساب المقفل
        ip_address = self.get_client_ip(request)
        email = request.data.get('email')
        
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                if user.is_account_locked():
                    return Response(
                        {"error": "Account is temporarily locked. Try again later."}, 
                        status=status.HTTP_423_LOCKED
                    )
            except CustomUser.DoesNotExist:
                pass

        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            # نجح تسجيل الدخول
            user = CustomUser.objects.get(email=email)
            user.failed_login_attempts = 0
            user.last_login_ip = ip_address
            user.account_locked_until = None
            user.save()
            
            logger.info(f"Successful login for user: {email} from IP: {ip_address}")
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        else:
            # فشل تسجيل الدخول
            if email:
                try:
                    user = CustomUser.objects.get(email=email)
                    user.failed_login_attempts += 1
                    
                    # قفل الحساب بعد 5 محاولات فاشلة
                    if user.failed_login_attempts >= 5:
                        user.account_locked_until = timezone.now() + timedelta(minutes=15)
                    
                    user.save()
                    logger.warning(f"Failed login attempt for user: {email} from IP: {ip_address}")
                except CustomUser.DoesNotExist:
                    pass
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            from rest_framework_simplejwt.tokens import RefreshToken, TokenError
            
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Refresh token is required."}, 
                    status=status.HTTP_400_BAD_REQUEST)
            
            # إنهاء الجلسة في قاعدة البيانات
            if not request.user.allows_multiple_devices():
                device_fingerprint = generate_device_fingerprint(request)
                UserSession.objects.filter(
                    user=request.user,
                    device_fingerprint=device_fingerprint,
                    is_active=True
                ).update(is_active=False)
            
            # Blacklist الـ token
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            logger.info(f"User logged out: {request.user.email}")
            return Response({"detail": "Logout successful."}, 
                status=status.HTTP_205_RESET_CONTENT)
            
        except TokenError:
            return Response({"error": "Invalid or expired token."}, 
                status=status.HTTP_400_BAD_REQUEST)




logger = logging.getLogger(__name__)

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            # تسجيل العملية
            logger.info(f"Password changed for user: {user.email}")
            
            return Response({"detail": "Password changed successfully."}, 
                status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                return Response({"detail": "هذا البريد غير مسجل."}, status=status.HTTP_400_BAD_REQUEST)

            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

            reset_link = f"{settings.FRONTEND_URL}/reset-password/?uid={uidb64}&token={token}"

            try:
                send_mail(
                    'Password Reset',
                    f'Click the link below to reset your password:\n{reset_link}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                return Response({"detail": "تم إرسال رابط إعادة تعيين كلمة المرور إلى بريدك."},
                                status=status.HTTP_200_OK)
            except Exception as e:
                return Response({"error": "فشل إرسال البريد الإلكتروني."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordConfirmView(APIView):
    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not uid or not token or not new_password:
            return Response({"error": "بيانات غير مكتملة."}, status=400)

        try:
            uid = force_str(urlsafe_base64_decode(uid))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            return Response({"error": "رابط غير صالح."}, status=400)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({"error": "الرابط غير صالح أو منتهي الصلاحية."}, status=400)

        user.set_password(new_password)
        user.save()
        return Response({"detail": "تم تغيير كلمة المرور بنجاح."}, status=200)






class ActiveSessionsView(APIView):
    """عرض الجلسات النشطة للمستخدم"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sessions = UserSession.objects.filter(
            user=request.user,
            is_active=True
        ).exclude(is_expired=True)
        
        sessions_data = []
        for session in sessions:
            sessions_data.append({
                'id': session.id,
                'ip_address': session.ip_address,
                'user_agent': session.user_agent[:100],  # أول 100 حرف
                'created_at': session.created_at,
                'last_activity': session.last_activity,
                'is_current': session.device_fingerprint == generate_device_fingerprint(request)
            })
        
        return Response({
            'active_sessions': sessions_data,
            'allows_multiple_devices': request.user.allows_multiple_devices()
        })

    def delete(self, request):
        """إنهاء جلسة معينة"""
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({"error": "Session ID is required."}, 
                status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = UserSession.objects.get(
                id=session_id,
                user=request.user,
                is_active=True
            )
            session.is_active = False
            session.save()
            
            return Response({"detail": "Session terminated successfully."})
            
        except UserSession.DoesNotExist:
            return Response({"error": "Session not found."}, 
                status=status.HTTP_404_NOT_FOUND)