# في ملف middleware.py جديد
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from .models import UserSession

class SingleDeviceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # تجاهل الـ endpoints اللي مش محتاجة authentication
        if request.path in ['/users/login/', '/users/register/', '/users/forgot-password/','/users/reset-password-confirm/','/admin/','/api/create-payment/']:
            return self.get_response(request)

        # التحقق من التوكن
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(auth_header.split(' ')[1])
                user = jwt_auth.get_user(validated_token)
                jti = validated_token['jti']

                # للطلاب فقط: التحقق من الجلسة
                if not user.allows_multiple_devices():
                    session = UserSession.objects.filter(
                        user=user, 
                        session_key=jti, 
                        is_active=True
                    ).first()

                    if not session:
                        return Response(
                            {"error_message": "Session expired. Please login again."},
                            status=401
                        )
                    
                    # تحديث آخر نشاط
                    session.last_activity = timezone.now()
                    session.save()

            except Exception:
                pass

        return self.get_response(request)