# users/decorators.py
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import redirect_to_login

def org_admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated:
            return redirect_to_login(next=request.get_full_path())
        if not getattr(u, "is_org_admin", False) or not getattr(u, "organization_id", None):
            # ไม่ใช่ผู้ดูแลองค์กร หรือยังไม่สังกัดองค์กร
            raise PermissionDenied("สำหรับผู้ดูแลองค์กรเท่านั้น")
        return view_func(request, *args, **kwargs)
    return _wrapped
