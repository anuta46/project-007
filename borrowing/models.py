from django.db import models
from users.models import Organization, CustomUser
from django.db.models import Sum, F

class Item(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="องค์กร")
    name = models.CharField(max_length=255, verbose_name="ชื่อประเภทสิ่งของ")
    description = models.TextField(blank=True, verbose_name="รายละเอียด")
    # เปลี่ยน quantity เป็น total_quantity เพื่อให้สอดคล้องกับ Asset
    total_quantity = models.IntegerField(default=0, verbose_name="จำนวนทั้งหมด") 
    available_quantity = models.IntegerField(default=0, verbose_name="จำนวนที่เหลืออยู่")
    
    image = models.ImageField(upload_to='item_images/', blank=True, null=True, verbose_name="รูปภาพสิ่งของ")
    item_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="ประเภทสิ่งของ")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่เพิ่ม")

    class Meta:
        verbose_name = "ประเภทสิ่งของ"
        verbose_name_plural = "ประเภทสิ่งของ"
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    # เพิ่มเมธอดสำหรับอัปเดตจำนวนทั้งหมดและจำนวนที่เหลืออยู่ของ Item
    def update_quantities(self):
        # นับจำนวน Asset ทั้งหมดที่ผูกกับ Item นี้
        self.total_quantity = self.assets.count()
        # นับจำนวน Asset ที่มีสถานะ 'available'
        self.available_quantity = self.assets.filter(status='available').count()
        self.save()

class Asset(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='assets', verbose_name="ประเภทสิ่งของ")
    serial_number = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name="หมายเลขซีเรียล")
    device_id = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name="ID อุปกรณ์")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="ตำแหน่ง")
    STATUS_CHOICES = [
        ('available', 'พร้อมใช้งาน'),
        ('on_loan', 'กำลังถูกยืม'),
        ('maintenance', 'บำรุงรักษา'),
        ('retired', 'ปลดระวาง'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', verbose_name="สถานะ")

    class Meta:
        verbose_name = "อุปกรณ์"
        verbose_name_plural = "อุปกรณ์"
        
    def __str__(self):
        identifier = self.serial_number or self.device_id or f"Asset {self.id}"
        return f"{self.item.name} ({identifier}) - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # ตรวจสอบว่ามี serial_number หรือ device_id อย่างน้อยหนึ่งอย่าง
        if not self.serial_number and not self.device_id:
            raise ValueError("ต้องระบุหมายเลขซีเรียลหรือ ID อุปกรณ์อย่างใดอย่างหนึ่ง")
        super().save(*args, **kwargs)
        # อัปเดต Item quantities หลังจาก Asset ถูกบันทึก
        self.item.update_quantities()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        # อัปเดต Item quantities หลังจาก Asset ถูกลบ
        self.item.update_quantities()


class Loan(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, verbose_name="อุปกรณ์") # เปลี่ยนจาก item เป็น asset
    borrower = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="ผู้ยืม")
    borrow_date = models.DateTimeField(auto_now_add=True, verbose_name="วันที่ยืม")
    due_date = models.DateField(verbose_name="กำหนดคืน") # ใช้ DateField สำหรับวันที่เท่านั้น
    return_date = models.DateTimeField(null=True, blank=True, verbose_name="วันที่คืน")
    STATUS_CHOICES = [
        ('pending', 'รอดำเนินการ'),
        ('approved', 'อนุมัติแล้ว'),
        ('returned', 'คืนแล้ว'),
        ('rejected', 'ถูกปฏิเสธ'),
        ('overdue', 'เกินกำหนด'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="สถานะ")
    reason = models.TextField(blank=True, verbose_name="เหตุผลการยืม") # เพิ่มฟิลด์เหตุผลการยืม

    class Meta:
        verbose_name = "รายการยืม"
        verbose_name_plural = "รายการยืม"
        ordering = ['-borrow_date']

    def __str__(self):
        return f"Loan of {self.asset.item.name} ({self.asset.serial_number or self.asset.device_id}) by {self.borrower.username} - Status: {self.status}"
