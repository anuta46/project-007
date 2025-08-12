# users/forms.py

from django import forms
from .models import Organization, CustomUser # นำเข้าโมเดล Organization และ CustomUser

# ฟอร์มสำหรับข้อมูลองค์กร
class OrganizationRegistrationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'address', 'business_type']
        # สามารถเพิ่ม widgets เพื่อปรับแต่งรูปแบบ input ได้ตามต้องการ
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'business_type': forms.TextInput(attrs={'placeholder': 'เช่น เทคโนโลยี, การศึกษา, การผลิต'})
        }

# ฟอร์มสำหรับข้อมูลผู้ใช้ที่จะเป็นแอดมินองค์กรคนแรก
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="รหัสผ่าน")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="ยืนยันรหัสผ่าน")

    class Meta:
        model = CustomUser
        fields = ['username', 'email']
        labels = {
            'username': "ชื่อผู้ใช้งาน",
            'email': "อีเมล",
        }

    # ตรวจสอบว่ารหัสผ่านและยืนยันรหัสผ่านตรงกัน
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            # หากรหัสผ่านไม่ตรงกัน ให้เพิ่มข้อผิดพลาด
            raise forms.ValidationError("รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน")
        return cleaned_data

    # บันทึกผู้ใช้โดยใช้ create_user เพื่อให้รหัสผ่านถูก Hash
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
