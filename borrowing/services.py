# borrowing/services.py
from django.utils import timezone
from django.db import transaction
from .models import Loan

def approve_loan(loan: Loan):
    """อนุมัติ -> เซ็ต approved และ timestamp; (ถ้าคุณมี field สถานะใน Asset จะไปปรับตอนรับของจริง/หรืออนุมัติเลยก็ได้)"""
    with transaction.atomic():
        if loan.status != 'pending':
            return False, "สถานะไม่ใช่รอดำเนินการ"
        loan.status = 'approved'
        if not loan.approved_at:
            loan.approved_at = timezone.now()
        loan.save(update_fields=['status', 'approved_at'])
        # หมายเหตุ: ถ้าต้องการกันของทันทีตั้งแต่อนุมัติ ให้ไปอัพเดต asset.status ที่ view/service อื่นตามนโยบายคุณ
        return True, None

def reject_loan(loan: Loan):
    with transaction.atomic():
        if loan.status != 'pending':
            return False, "สถานะไม่ใช่รอดำเนินการ"
        loan.status = 'rejected'
        loan.save(update_fields=['status'])
        return True, None

def return_loan(loan: Loan):
    """รับคืน -> returned และ (ถ้าคุณใช้ field สถานะใน Asset) ปล่อยของเป็น available"""
    with transaction.atomic():
        if loan.status not in ('approved', 'overdue'):
            return False, "สถานะนี้คืนไม่ได้"
        loan.status = 'returned'
        loan.return_date = timezone.now()
        loan.save(update_fields=['status', 'return_date'])

        # ถ้าโมเดล Asset ของคุณมีฟิลด์ status ให้ปล่อยของกลับ available ที่นี่
        if hasattr(loan.asset, 'status'):
            try:
                loan.asset.status = 'available'
                loan.asset.save(update_fields=['status'])
            except Exception:
                pass
        return True, None
