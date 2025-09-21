# users/utils.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

def get_admin_org(request):
    """ใช้เฉพาะฝั่งแอดมิน: ดึงองค์กรของผู้ใช้ ถ้าไม่มีสิทธิ์ให้ error"""
    u = request.user
    if not (u.is_authenticated and getattr(u, "is_org_admin", False) and getattr(u, "organization_id", None)):
        raise PermissionDenied("สำหรับผู้ดูแลองค์กรเท่านั้น")
    return u.organization

def org_get_or_404(model, user, **kwargs):
    """
    get_object_or_404 สำหรับโมเดลที่มี FK ไป organization (ตรงหรือผ่านความสัมพันธ์)
    ใช้ตอนแก้/ลบ/อนุมัติ เพื่อกันข้ามองค์กร
    """
    return get_object_or_404(model, **kwargs)
