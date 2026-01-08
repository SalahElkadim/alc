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
from .models import CustomUser
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import render
from .models import PasswordResetRequest
from rest_framework.permissions import AllowAny


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

logger = logging.getLogger(__name__)

class LoginView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        ip_address = self.get_client_ip(request)
        email = request.data.get('email')

        if not email:
            return Response(
                {"error_message": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user exists
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            logger.warning(f"Login failed for non-existing user: {email}")
            return Response(
                {"error_message": "Invalid credentials."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if account is locked
        if user.is_account_locked():
            return Response(
                {"error_message": "Account is temporarily locked. Try again later."},
                status=status.HTTP_423_LOCKED
            )
        
        # Validate password
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.account_locked_until = timezone.now() + timedelta(minutes=15)
            user.save()
            message = serializer.errors.get('error_message', ["Invalid credentials."])[0]
            return Response({"error_message": message}, status=status.HTTP_400_BAD_REQUEST)

        # Successful login
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.last_login_ip = ip_address
        user.save()

        logger.info(f"✅ Successful login for {email} from IP: {ip_address}")
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error_message": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Blacklist the token
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"detail": "Logout successful."},
                status=status.HTTP_205_RESET_CONTENT
            )

        except TokenError:
            return Response(
                {"error_message": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )

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
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']

            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                return Response({"error_message": "This email is not registered."}, status=400)

            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

            reset_link = f"https://alcreactapp-production.up.railway.app/users/reset-password-confirm/{uidb64}/{token}/"

            # Save the request instead of sending
            PasswordResetRequest.objects.create(
                email=email,
                reset_link=reset_link
            )

            return Response({
                "detail": "Password reset request has been sent. An administrator will respond to you soon.",
            }, status=200)

        return Response(serializer.errors, status=400)

class ResetPasswordConfirmView(APIView):
    permission_classes = []
    authentication_classes = [] 
    
    def post(self, request, uid, token):
        new_password = request.data.get("new_password")
        
        if not new_password:
            return Response({"error_message": "Password is required."}, status=400)
        
        # Add password validation
        if len(new_password) < 8:
            return Response({"error_message": "Password must be at least 8 characters long."}, status=400)
        
        try:
            uid_decoded = force_str(urlsafe_base64_decode(uid))
            user = CustomUser.objects.get(pk=uid_decoded)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            return Response({"error_message": "Invalid link."}, status=400)
        
        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({"error_message": "Invalid or expired link."}, status=400)
        
        user.set_password(new_password)
        user.save()
        return Response({"detail": "Password has been changed successfully."}, status=200)

class CustomTokenRefreshView(TokenRefreshView):
    """
    Use the standard TokenRefreshView from simplejwt
    Refreshes the access token using the refresh token
    """
    pass 

def custom_404(request, exception):
    return render(request, "errors/404.html", status=404)

def privacy(request):
    return render(request, "privacy.html")

def support(request):
    return render(request, "support.html")

from rest_framework.permissions import IsAdminUser
from .models import PasswordResetRequest
from .serializers import PasswordResetRequestSerializer

class PasswordResetRequestList(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        requests = PasswordResetRequest.objects.all().order_by('-created_at')
        serializer = PasswordResetRequestSerializer(requests, many=True)
        return Response(serializer.data)

    def patch(self, request, pk):
        try:
            req = PasswordResetRequest.objects.get(pk=pk)
            req.is_handled = request.data.get("is_handled", True)
            req.save()
            return Response({"detail": "Status updated successfully."})
        except PasswordResetRequest.DoesNotExist:
            return Response({"error": "Request not found."}, status=404)

class DeleteUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response(
                {"error_message": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify that the user is deleting their own account or is an admin
        if request.user.email != email and not request.user.is_staff:
            return Response(
                {"error_message": "You are not authorized to delete this account."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Prevent deleting admin accounts unless by another admin
            if user.is_staff and not request.user.is_superuser:
                return Response(
                    {"error_message": "Cannot delete administrator account."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            user_email = user.email
            user.delete()
            
            logger.info(f"User account deleted: {user_email} by {request.user.email}")
            
            return Response(
                {"detail": "Account deleted successfully."},
                status=status.HTTP_200_OK
            )
            
        except CustomUser.DoesNotExist:
            return Response(
                {"error_message": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )