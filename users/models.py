# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

# โมเดลสำหรับข้อมูลองค์กร
class Organization(models.Model):
    name = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=255)
    business_type = models.CharField(max_length=100)
    # เพิ่มฟิลด์อื่นๆ ที่จำเป็นสำหรับองค์กรได้ในภายหลัง

    def __str__(self):
        return self.name

# โมเดลสำหรับผู้ใช้งาน (Custom User Model)
class CustomUser(AbstractUser):
    # เชื่อมโยงผู้ใช้งานกับองค์กรที่สังกัด
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    # กำหนดบทบาทของผู้ใช้งาน
    # True = Platform Admin, False = ไม่ใช่
    is_platform_admin = models.BooleanField(default=False)
    # True = Organization Admin, False = ไม่ใช่
    is_org_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.username