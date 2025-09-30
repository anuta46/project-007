# borrowing/models.py
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from users.models import Organization, CustomUser


class ItemCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อหมวดหมู่")
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=50, blank=True, verbose_name="ไอคอน (เช่น fa-laptop)")

    class Meta:
        verbose_name = "หมวดอุปกรณ์"
        verbose_name_plural = "หมวดอุปกรณ์"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Item(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, verbose_name="องค์กร", db_index=True
    )
    name = models.CharField(max_length=255, verbose_name="ชื่อประเภทสิ่งของ")
    description = models.TextField(blank=True, verbose_name="รายละเอียด")
    total_quantity = models.IntegerField(default=0, verbose_name="จำนวนทั้งหมด")
    available_quantity = models.IntegerField(default=0, verbose_name="จำนวนที่เหลืออยู่")
    image = models.ImageField(upload_to='item_images/', blank=True, null=True, verbose_name="รูปภาพสิ่งของ")
    category = models.ForeignKey(
        ItemCategory, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='items',
        verbose_name="หมวดอุปกรณ์"
    )
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่เพิ่ม")

    class Meta:
        verbose_name = "ประเภทสิ่งของ"
        verbose_name_plural = "ประเภทสิ่งของ"
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'name'],
                name='unique_item_name_per_org'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class Asset(models.Model):
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name='assets',
        verbose_name="ประเภทสิ่งของ", db_index=True
    )
    serial_number = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name="หมายเลขซีเรียล")
    device_id = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name="ID อุปกรณ์")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="ตำแหน่ง")
    added_at = models.DateTimeField(
        auto_now_add=True, db_index=True, null=True, verbose_name="วันที่เพิ่มเข้าระบบ"
    )

    STATUS_CHOICES = [
        ('available', 'พร้อมใช้งาน'),
        ('on_loan', 'กำลังถูกยืม'),
        ('maintenance', 'บำรุงรักษา'),
        ('retired', 'ปลดระวาง'),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='available', verbose_name="สถานะ", db_index=True
    )

    class Meta:
        verbose_name = "อุปกรณ์"
        verbose_name_plural = "อุปกรณ์"
        constraints = [
            models.CheckConstraint(
                check=Q(serial_number__isnull=False) | Q(device_id__isnull=False),
                name="asset_sn_or_deviceid_required",
            ),
        ]

    def __str__(self):
        identifier = self.serial_number or self.device_id or f"Asset {self.id}"
        return f"{self.item.name} ({identifier}) - {self.get_status_display()}"

    def clean(self):
        sn = (self.serial_number or '').strip()
        did = (self.device_id or '').strip()
        if not sn and not did:
            raise ValidationError("ต้องระบุหมายเลขซีเรียลหรือ ID อุปกรณ์อย่างใดอย่างหนึ่ง")

    def save(self, *args, **kwargs):
        # normalize '' -> None
        if self.serial_number == '':
            self.serial_number = None
        if self.device_id == '':
            self.device_id = None

        old_item_id, old_status = None, None
        if self.pk:
            old = Asset.objects.only('item_id', 'status').get(pk=self.pk)
            old_item_id, old_status = old.item_id, old.status

        super().save(*args, **kwargs)

        # อัปเดตยอดฝั่ง Item เมื่อมีผลกระทบ
        affected_item_ids = {self.item_id}
        if old_item_id and old_item_id != self.item_id:
            affected_item_ids.add(old_item_id)
        if old_status != self.status or len(affected_item_ids) > 1:
            for iid in affected_item_ids:
                total = Asset.objects.filter(item_id=iid).count()
                available = Asset.objects.filter(item_id=iid, status='available').count()
                Item.objects.filter(pk=iid).update(
                    total_quantity=total,
                    available_quantity=available
                )

    def delete(self, *args, **kwargs):
        item_id = self.item_id
        super().delete(*args, **kwargs)
        total = Asset.objects.filter(item_id=item_id).count()
        available = Asset.objects.filter(item_id=item_id, status='available').count()
        Item.objects.filter(pk=item_id).update(
            total_quantity=total,
            available_quantity=available
        )


class Loan(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, verbose_name="อุปกรณ์", related_name='loans', db_index=True)
    borrower = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="ผู้ยืม", related_name='loans', db_index=True)

    borrow_date = models.DateTimeField(auto_now_add=True, verbose_name="วันที่ส่งคำขอ")
    start_date = models.DateField(null=True, blank=True, verbose_name="วันที่เริ่มใช้ (จอง)")
    due_date = models.DateField(null=True, blank=True, verbose_name="กำหนดคืน")

    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="วันที่อนุมัติ")
    pickup_date = models.DateTimeField(null=True, blank=True, verbose_name="วันที่รับของจริง")
    return_date = models.DateTimeField(null=True, blank=True, verbose_name="วันที่คืน")

    STATUS_CHOICES = [
        ('pending', 'รอดำเนินการ'),
        ('approved', 'อนุมัติแล้ว/จองสำเร็จ'),
        ('returned', 'คืนแล้ว'),
        ('rejected', 'ถูกปฏิเสธ'),
        ('overdue', 'เกินกำหนด'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="สถานะ", db_index=True)
    reason = models.TextField(blank=True, verbose_name="เหตุผลการยืม")

    class Meta:
        verbose_name = "รายการยืม"
        verbose_name_plural = "รายการยืม"
        ordering = ['-borrow_date']
        indexes = [
            models.Index(fields=['asset', 'status']),
            models.Index(fields=['asset', 'start_date', 'due_date']),
        ]

    def __str__(self):
        rng = ""
        if self.start_date and self.due_date:
            rng = f" [{self.start_date} → {self.due_date}]"
        return f"Loan #{self.pk} {self.asset} by {self.borrower}{rng}"

    def clean(self):
        super().clean()

        errors = {}

        # 1) ตรวจช่วงวันพื้นฐาน
        if self.start_date and self.due_date:
            if self.due_date < self.start_date:
                errors['due_date'] = ValidationError("กำหนดคืนต้องไม่น้อยกว่าวันเริ่มใช้")

        # 2) สถานะที่ต้องมีช่วงวัน
        if self.status in ('approved', 'overdue'):
            if not self.start_date:
                errors['start_date'] = ValidationError("สถานะนี้ต้องระบุวันที่เริ่มใช้")
            if not self.due_date:
                errors['due_date'] = ValidationError("สถานะนี้ต้องระบุกำหนดคืน")

        # 3) กันการจอง/อนุมัติซ้อนช่วงกับสินทรัพย์เดียวกัน
        if self.start_date and self.due_date and self.asset_id:
            overlapping_qs = Loan.objects.filter(
                asset_id=self.asset_id,
                status__in=['pending', 'approved']
            ).exclude(pk=self.pk).filter(
                Q(start_date__lte=self.due_date) & Q(due_date__gte=self.start_date)
            )
            if overlapping_qs.exists():
                errors['start_date'] = ValidationError("ช่วงเวลานี้ทับกับการจอง/อนุมัติเดิมของอุปกรณ์ชิ้นนี้")
                errors['due_date'] = ValidationError("กรุณาเลือกช่วงอื่นที่ไม่ทับซ้อน")

        if errors:
            raise ValidationError(errors)
