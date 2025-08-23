# borrowing/models.py
from django.db import models
from users.models import Organization, CustomUser

class Item(models.Model):
    # ฟิลด์ที่อธิบายถึง "ประเภท" ของสิ่งของ (เช่น Laptop, Projector, Book)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, verbose_name="องค์กร")
    name = models.CharField(max_length=255, verbose_name="ชื่อประเภทสิ่งของ")
    description = models.TextField(blank=True, verbose_name="รายละเอียดประเภทสิ่งของ")
    
    # ฟิลด์รูปภาพของ "ประเภทสิ่งของ"
    image = models.ImageField(upload_to='item_images/', blank=True, null=True, verbose_name="รูปภาพประเภทสิ่งของ")
    
    # ฟิลด์ประเภทสิ่งของ (เช่น "อุปกรณ์อิเล็กทรอนิกส์", "หนังสือ") - เป็นฟิลด์ของ Item (ประเภท)
    item_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="ประเภทกลุ่มสิ่งของ")

    # ฟิลด์สำหรับเก็บเวลาที่ "ประเภทสิ่งของ" นี้ถูกเพิ่ม
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่เพิ่มประเภทสิ่งของ")

    class Meta:
        verbose_name = "ประเภทสิ่งของ" 
        verbose_name_plural = "ประเภทสิ่งของ"
        unique_together = ('organization', 'name') # ตรวจสอบให้ชื่อประเภทสิ่งของในแต่ละองค์กรไม่ซ้ำกัน

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    # เพิ่ม property เพื่อคำนวณจำนวน Assets ที่มีอยู่ทั้งหมดของ Item นี้
    @property
    def total_quantity(self):
        return self.assets.count()

    # เพิ่ม property เพื่อคำนวณจำนวน Assets ที่พร้อมให้ยืมของ Item นี้
    @property
    def available_quantity(self):
        return self.assets.filter(status='available').count()


# โมเดลใหม่สำหรับ "อุปกรณ์แต่ละชิ้น" (Individual Asset)
class Asset(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='assets', verbose_name="ประเภทสิ่งของ")
    
    # หมายเลขประจำเครื่อง (Serial Number) - สามารถว่างได้ และไม่บังคับว่าต้อง unique ถ้าว่าง
    serial_number = models.CharField(max_length=255, blank=True, null=True, verbose_name="หมายเลขประจำเครื่อง (Serial Number)")
    
    # รหัสอุปกรณ์ (Device ID) - สามารถว่างได้
    device_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="รหัสอุปกรณ์ (Device ID)")
    
    # สถานที่จัดเก็บของ Asset ชิ้นนี้
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="สถานที่จัดเก็บ")
    
    CONDITION_CHOICES = [
        ('excellent', 'ดีเยี่ยม'),
        ('good', 'ดี'),
        ('fair', 'พอใช้'),
        ('poor', 'ชำรุด'),
    ]
    # สภาพของ Asset ชิ้นนี้
    condition = models.CharField(max_length=50, choices=CONDITION_CHOICES, default='good', verbose_name="สภาพสิ่งของ")

    ASSET_STATUS_CHOICES = [
        ('available', 'พร้อมให้ยืม'),
        ('on_loan', 'กำลังถูกยืม'),
        ('in_repair', 'อยู่ระหว่างซ่อม'),
        ('retired', 'ปลดประจำการ'),
        ('lost', 'สูญหาย'),
    ]
    # สถานะของ Asset ชิ้นนี้
    status = models.CharField(max_length=50, choices=ASSET_STATUS_CHOICES, default='available', verbose_name="สถานะ Asset")

    class Meta:
        verbose_name = "อุปกรณ์แต่ละชิ้น"
        verbose_name_plural = "อุปกรณ์แต่ละชิ้น"

    def __str__(self):
        # แสดงผลตาม Serial Number หรือ Device ID หากมี
        if self.serial_number:
            return f"{self.item.name} (SN: {self.serial_number})"
        elif self.device_id:
            return f"{self.item.name} (ID: {self.device_id})"
        else:
            return f"{self.item.name} (Asset {self.id})"


class Loan(models.Model):
    # เปลี่ยน Item เป็น Asset เพราะการยืมจะผูกกับอุปกรณ์แต่ละชิ้น
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, verbose_name="อุปกรณ์ที่ยืม")
    borrower = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="ผู้ยืม")
    borrow_date = models.DateTimeField(auto_now_add=True, verbose_name="วันที่ยืม")
    due_date = models.DateField(verbose_name="กำหนดคืน")
    return_date = models.DateTimeField(null=True, blank=True, verbose_name="วันที่คืน")
    
    # เพิ่มฟิลด์สำหรับเหตุผลในการยืม
    reason = models.TextField(blank=True, verbose_name="เหตุผลในการยืม")

    STATUS_CHOICES = [
        ('pending', 'รอดำเนินการ'),
        ('approved', 'อนุมัติแล้ว'),
        ('returned', 'คืนแล้ว'),
        ('rejected', 'ถูกปฏิเสธ'),
        ('overdue', 'เกินกำหนด'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="สถานะ")

    class Meta:
        verbose_name = "รายการยืม"
        verbose_name_plural = "รายการยืม"
        ordering = ['-borrow_date']

    def __str__(self):
        return f"Loan of {self.asset.item.name} ({self.asset.serial_number or self.asset.device_id or self.asset.id}) by {self.borrower.username} - Status: {self.status}"
