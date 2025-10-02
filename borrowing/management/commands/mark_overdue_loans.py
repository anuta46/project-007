# borrowing/management/commands/mark_overdue_loans.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from borrowing.models import Loan

class Command(BaseCommand):
    help = "มาร์กคำยืมที่กำหนดคืนแล้วแต่ยังไม่คืนเป็นสถานะ overdue (ไม่มีการแจ้งเตือน)"

    def handle(self, *args, **options):
        today = timezone.localdate()  # เนื่องจาก due_date เป็น DateField
        qs = Loan.objects.filter(status='approved', due_date__lt=today)
        updated = 0
        for loan in qs:
            loan.status = 'overdue'
            loan.save(update_fields=['status'])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Overdue updated: {updated}"))
