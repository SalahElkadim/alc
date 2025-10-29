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
from .models import CustomUser, UserSession
from .utils import generate_device_fingerprint
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import render


logger = logging.getLogger(__name__)


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
        ip_address = self.get_client_ip(request)
        email = request.data.get('email')

        # ✅ فحص إذا كان المستخدم مسجل دخول فعلاً
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            try:
                jwt_auth = JWTAuthentication()
                token = auth_header.split(' ')[1]
                validated_token = jwt_auth.get_validated_token(token)
                current_user = jwt_auth.get_user(validated_token)
                jti = validated_token['jti']
                
                # تحقق من وجود جلسة نشطة
                active_session = UserSession.objects.filter(
                    user=current_user,
                    session_key=jti,
                    is_active=True
                ).exists()
                
                if active_session:
                    return Response(
                        {"error_message": "You are already logged in. Please logout first."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except:
                pass  # التوكن منتهي أو غلط، كمل عادي

        # فحص Account Lock
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                if user.is_account_locked():
                    return Response(
                        {"error_message": "Account is temporarily locked. Try again later."},
                        status=status.HTTP_423_LOCKED
                    )
            except CustomUser.DoesNotExist:
                pass

        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = CustomUser.objects.get(email=email)
            
            # ✅ إلغاء الجلسات القديمة **قبل** إنشاء التوكن
            if not user.allows_multiple_devices():
                UserSession.objects.filter(user=user, is_active=True).update(is_active=False)
            
            user.failed_login_attempts = 0
            user.last_login_ip = ip_address
            user.account_locked_until = None
            user.save()

            device_fingerprint = generate_device_fingerprint(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            access_token = serializer.validated_data['tokens']['access']

            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(access_token)
            session_key = validated_token['jti']
            
            UserSession.objects.create(
                user=user,
                session_key=session_key,
                device_fingerprint=device_fingerprint,
                ip_address=ip_address,
                user_agent=user_agent,
                is_active=True
            )

            logger.info(f"Successful login for user: {email} from IP: {ip_address}")
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        else:
            if email:
                try:
                    user = CustomUser.objects.get(email=email)
                    user.failed_login_attempts += 1
                    if user.failed_login_attempts >= 5:
                        user.account_locked_until = timezone.now() + timedelta(minutes=15)
                    user.save()
                    logger.warning(f"Failed login attempt for user: {email} from IP: {ip_address}")
                except CustomUser.DoesNotExist:
                    pass

            errors = serializer.errors
            if 'error_message' in errors:
                message = errors['error_message']
                if isinstance(message, list):
                    message = message[0]
                errors = {'error_message': message}
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error_message": "Refresh token is required."},
                                status=status.HTTP_400_BAD_REQUEST)

            # ✅ إلغاء الجلسة قبل تدمير التوكن
            if not request.user.allows_multiple_devices():
                # الحصول على jti من access token الحالي
                auth_header = request.META.get('HTTP_AUTHORIZATION', '')
                if auth_header.startswith('Bearer '):
                    jwt_auth = JWTAuthentication()
                    validated_token = jwt_auth.get_validated_token(auth_header.split(' ')[1])
                    jti = validated_token['jti']
                    
                    UserSession.objects.filter(
                        user=request.user,
                        session_key=jti,
                        is_active=True
                    ).update(is_active=False)

            token = RefreshToken(refresh_token)
            token.blacklist()

            logger.info(f"User logged out: {request.user.email}")
            return Response({"detail": "Logout successful."},
                            status=status.HTTP_205_RESET_CONTENT)

        except TokenError:
            return Response({"error_message": "Invalid or expired token."},
                            status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()

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
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = [] 
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                return Response({"error_message": "هذا البريد غير مسجل."}, status=status.HTTP_400_BAD_REQUEST)

            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

            reset_link = f"https://alcreactapp-production.up.railway.app/users/reset-password-confirm/{uidb64}/{token}/"
            #reset_link = f"http://127.0.0.1:8000/users/reset-password-confirm/{uidb64}/{token}/"

            print("📧 Attempting to send email...")
            send_mail(
                    subject='Password Reset',
                    message= 'hello',
                    #message=f'Click the link below to reset your password:\n{reset_link}',
                    from_email= 'salah.mohamed.elkadim@gmail.com',
                    recipient_list = ['sm249481@gmail.com'],
                    
                )
            return Response({"detail": "تم إرسال رابط إعادة تعيين كلمة المرور إلى بريدك."},status=status.HTTP_200_OK)


        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordConfirmView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = [] 
    def post(self, request, uid, token):  # إضافة uid وtoken كـ parameters
        new_password = request.data.get("new_password")
        
        if not new_password:
            return Response({"error_message": "كلمة المرور مطلوبة."}, status=400)
        
        # إضافة validation لكلمة المرور
        if len(new_password) < 8:
            return Response({"error_message": "كلمة المرور يجب أن تكون 8 أحرف على الأقل."}, status=400)
        
        try:
            uid_decoded = force_str(urlsafe_base64_decode(uid))
            user = CustomUser.objects.get(pk=uid_decoded)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            return Response({"error_message": "رابط غير صالح."}, status=400)
        
        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({"error_message": "الرابط غير صالح أو منتهي الصلاحية."}, status=400)
        
        user.set_password(new_password)
        user.save()
        return Response({"detail": "تم تغيير كلمة المرور بنجاح."}, status=200)


class ActiveSessionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sessions = UserSession.objects.filter(user=request.user, is_active=True)
        active_sessions = [
            s for s in sessions
            if timezone.now() - s.last_activity <= timedelta(minutes=30)
        ]
        sessions_data = []
        for session in active_sessions:
            sessions_data.append({
                'id': session.id,
                'ip_address': session.ip_address,
                'user_agent': session.user_agent[:100],
                'created_at': session.created_at,
                'last_activity': session.last_activity,
                'is_current': session.device_fingerprint == generate_device_fingerprint(request)
            })

        return Response({
            'active_sessions': sessions_data,
            'allows_multiple_devices': request.user.allows_multiple_devices()
        })

    def delete(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({"error_message": "Session ID is required."},
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
            return Response({"error_message": "Session not found."},
                            status=status.HTTP_404_NOT_FOUND)

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200 and "access" in response.data:
            try:
                access_token = response.data["access"]
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(access_token)
                jti = validated_token["jti"]
                user = jwt_auth.get_user(validated_token)

                # ✅ للطلاب: التحقق من وجود جلسة نشطة
                if not user.allows_multiple_devices():
                    session = UserSession.objects.filter(
                        user=user, 
                        is_active=True
                    ).order_by('-last_activity').first()
                    
                    if session:
                        session.session_key = jti
                        session.last_activity = timezone.now()
                        session.save()
                    else:
                        # لو مفيش جلسة نشطة، ارفض التحديث
                        return Response(
                            {"error_message": "No active session. Please login again."},
                            status=401
                        )
            except Exception as e:
                logger.error(f"Error in token refresh: {str(e)}")
                
        return response

def custom_404(request, exception):
    return render(request, "errors/404.html", status=404)