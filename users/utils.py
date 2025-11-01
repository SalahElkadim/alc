import hashlib
import json
from django.utils import timezone

import hashlib
import json

def generate_device_fingerprint(request):
    """توليد بصمة دقيقة وفريدة للجهاز"""
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    connection = request.META.get('HTTP_CONNECTION', '')
    accept = request.META.get('HTTP_ACCEPT', '')
    upgrade_insecure = request.META.get('HTTP_UPGRADE_INSECURE_REQUESTS', '')
    timezone_offset = request.COOKIES.get('timezone', '')

    fingerprint_data = {
        'ip': ip_address,
        'user_agent': user_agent,
        'accept_language': accept_language,
        'accept_encoding': accept_encoding,
        'connection': connection,
        'accept': accept,
        'upgrade_insecure': upgrade_insecure,
        'timezone_offset': timezone_offset,
    }

    # توليد بصمة دقيقة
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