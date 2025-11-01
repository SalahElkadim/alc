from django.utils import timezone
from django.http import HttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .models import UserSession
import logging
import json

logger = logging.getLogger(__name__)

class SingleDeviceMiddleware:
    """
    Middleware للتحقق من أن الطالب بيستخدم جهاز واحد فقط
    """
    
    EXCLUDED_PATHS = [
        '/users/register/',
        '/users/logout/',
        '/users/forgot-password/',
        '/users/reset-password-confirm/',
        '/admin/',

    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_exclude(request):
            return self.get_response(request)

        session_response = self._check_session(request)
        if session_response:
            return session_response

        return self.get_response(request)

    def _should_exclude(self, request):
        return any(request.path.startswith(path) for path in self.EXCLUDED_PATHS)

    def _check_session(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None

        try:
            token = auth_header.split(' ')[1]
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            jti = validated_token['jti']

            if user.allows_multiple_devices():
                return None

            session = UserSession.objects.filter(
                user=user,
                session_key=jti,
                is_active=True
            ).first()

            if not session:
                logger.warning(f"Expired session for user: {user.email}")
                
                # ✅ استخدم HttpResponse مع JSON
                response_data = {
                    "error_message": "Your session has expired. Another device has logged in.",
                    "code": "SESSION_EXPIRED"
                }
                return HttpResponse(
                    json.dumps(response_data),
                    content_type='application/json',
                    status=401
                )

            # تحديث آخر نشاط
            if (timezone.now() - session.last_activity).seconds > 300:
                session.last_activity = timezone.now()
                session.save(update_fields=['last_activity'])

            return None

        except (InvalidToken, TokenError):
            return None
        except Exception as e:
            logger.error(f"Session check error: {str(e)}")
            return None