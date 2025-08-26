# users/forms.py

from django import forms # นำเข้าโมดูลฟอร์มจาก Django
from .models import Organization, CustomUser # นำเข้า models , CustomUser , Organization เพื่อใช้เป็นฐานข้อมูลของฟอร์ม

# ฟอร์มสำหรับข้อมูลองค์กร
class OrganizationRegistrationForm(forms.ModelForm): #ประกาศคลาสฟอร์มใหม่
    class Meta: # กำหนดเมตาดาต้าของฟอร์ม
        model = Organization # กำหนดโมเดลที่ฟอร์มนี้จะใช้
        fields = ['name', 'address', 'business_type']# กำหนดฟิลด์ที่ต้องการในฟอร์ม
        widgets = {# กำหนดวิดเจ็ตสำหรับฟิลด์ต่างๆ
            'address': forms.Textarea(attrs={'rows': 3}), # ใช้ Textarea สำหรับฟิลด์ address
            'business_type': forms.TextInput(attrs={'placeholder': 'เช่น เทคโนโลยี, การศึกษา, การผลิต'}) # ใช้ TextInput พร้อม placeholder สำหรับฟิลด์ business_type
        }

# ฟอร์มสำหรับข้อมูลผู้ใช้ที่จะเป็นแอดมินองค์กรคนแรก
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="รหัสผ่าน")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="ยืนยันรหัสผ่าน")

    class Meta:
        model = CustomUser
        fields = ['username', 'email' , "phone_number"] # เพิ่มฟิลด์ phone_number
        labels = {
            'username': "ชื่อผู้ใช้งาน",
            'email': "อีเมล",
            'phone_number': "หมายเลขโทรศัพท์",
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

# ฟอร์มใหม่สำหรับผู้ใช้ที่ลงทะเบียนผ่านลิงก์ (ไม่รวมฟิลด์องค์กร)
class LinkBasedUserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="รหัสผ่าน")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="ยืนยันรหัสผ่าน")

    class Meta:
        model = CustomUser
        fields = ['username', 'email' , 'phone_number'] # ไม่มีฟิลด์ organization เพราะจะผูกใน View
        labels = {
            'username': "ชื่อ-สกุล",
            'email': "อีเมล",
           'phone_number': "หมายเลขโทรศัพท์",
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
