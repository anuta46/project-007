# users/context_processors.py

from .models import Notification

def unread_notifications_count(request):
    """
    Context processor เพื่อส่งจำนวนการแจ้งเตือนที่ยังไม่ได้อ่านของผู้ใช้
    ไปยังทุกเทมเพลต
    """
    if request.user.is_authenticated:
        # ดึงจำนวนการแจ้งเตือนที่ยังไม่ได้อ่านสำหรับผู้ใช้ที่เข้าสู่ระบบ
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0} # หากผู้ใช้ยังไม่ได้ล็อกอิน ให้ส่ง 0
