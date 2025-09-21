from django.contrib.auth.models import AbstractUser
from django.db import models






class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="ชื่อองค์กร")
    address = models.TextField(verbose_name="ที่อยู่")
    business_type = models.CharField(max_length=255, verbose_name="ประเภทธุรกิจ", blank=True, null=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    class Meta:
        verbose_name = "องค์กร"
        verbose_name_plural = "องค์กร"

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    # เพิ่มฟิลด์ organization เพื่อเชื่อมโยงผู้ใช้กับองค์กร
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="องค์กร")
    
    # เพิ่มฟิลด์ is_org_admin เพื่อระบุว่าเป็นผู้ดูแลองค์กรหรือไม่
    is_org_admin = models.BooleanField(default=False, verbose_name="ผู้ดูแลองค์กร")
    
    # เพิ่มฟิลด์ is_platform_admin เพื่อระบุว่าเป็นผู้ดูแลระบบแพลตฟอร์มหรือไม่
    # ผู้ดูแลระบบแพลตฟอร์มควรเป็น is_superuser และ is_staff ด้วย
    is_platform_admin = models.BooleanField(default=False, verbose_name="ผู้ดูแลแพลตฟอร์ม")
    
    phone_number = models.CharField(max_length=20, blank=True, null=True) 
   
    # ... ฟิลด์เดิมของคุณ ...
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)  # << เพิ่มบรรทัดนี้
    

    class Meta:
        verbose_name = "ผู้ใช้งาน"
        verbose_name_plural = "ผู้ใช้งาน"
        
        # เพิ่ม unique_together หากต้องการให้ username และ organization ต้องไม่ซ้ำกัน (สำหรับผู้ใช้ทั่วไป)
        # แต่ถ้า is_platform_admin ไม่ควรผูกกับ organization
        # unique_together = ('username', 'organization') # อาจต้องพิจารณาเงื่อนไขนี้

    def __str__(self):
        return self.username

# เพิ่มโมเดล Notification ใหม่
class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications', verbose_name="ผู้รับ")
    message = models.TextField(verbose_name="ข้อความแจ้งเตือน")
    is_read = models.BooleanField(default=False, verbose_name="อ่านแล้ว")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="วันที่สร้าง")
    # คุณสามารถเพิ่มฟิลด์อื่นๆ เช่น type_of_notification (loan_request, loan_approved, etc.)
    # หรือ related_object (ForeignKey ไปยัง Loan/Item) ได้ในอนาคต

    class Meta:
        verbose_name = "การแจ้งเตือน"
        verbose_name_plural = "การแจ้งเตือน"
        ordering = ['-created_at'] # เรียงลำดับจากใหม่ไปเก่า

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:50]}..."
    
    
