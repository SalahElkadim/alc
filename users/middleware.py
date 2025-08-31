from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .models import UserSession
import json
from .utils import generate_device_fingerprint
from django.utils import timezone


class SingleDeviceMiddleware(MiddlewareMixin):
    """Middleware لفحص الجلسات النشطة"""
    
    def process_request(self, request):
        # تجاهل بعض المسارات
        excluded_paths = ['/users/login/', '/users/register/', '/admin/','/users/logout/','/users/change-password/','/token/refresh/','/api/create-payment/'
]
        if any(request.path.startswith(path) for path in excluded_paths):
            return None
        
        # فحص JWT token
        jwt_auth = JWTAuthentication()
        try:
            validated_token = jwt_auth.get_validated_token(
                jwt_auth.get_raw_token(jwt_auth.get_header(request))
            )
            user = jwt_auth.get_user(validated_token)
            
            # فحص المستخدمين العاديين فقط
            if not user.allows_multiple_devices():
                device_fingerprint = generate_device_fingerprint(request)
                session_key = str(validated_token)
                
                # البحث عن الجلسة
                try:
                    session = UserSession.objects.get(
                    user=user,
                    session_key=validated_token['jti'],
                    device_fingerprint=device_fingerprint,
                    is_active=True
                )
                    
                    # تحديث آخر نشاط
                    session.last_activity = timezone.now()
                    session.save()
                    
                except UserSession.DoesNotExist:
                    # الجلسة غير موجودة أو تم إنهاؤها
                    return JsonResponse({
                        "error": "Session invalid. Please login again.",
                        "code": "SESSION_TERMINATED"
                    }, status=401)
                    
        except (InvalidToken, TokenError, AttributeError):
            # لا يوجد token أو token غير صحيح
            pass
            
        return None
