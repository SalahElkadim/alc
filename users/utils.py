import hashlib
import json
from django.utils import timezone

def generate_device_fingerprint(request):
    """إنشاء بصمة فريدة للجهاز"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    
    # يمكن إضافة المزيد من البيانات للدقة أكثر
    fingerprint_data = {
        'user_agent': user_agent,
        'accept_language': accept_language,
        'accept_encoding': accept_encoding,
    }
    
    # إنشاء hash فريد
    fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()


def get_client_ip(request):
    """الحصول على IP address الخاص بالعميل"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip