# users/forms.py

from django import forms
from .models import Organization, CustomUser


# ----------------------------
# ฟอร์ม: ลงทะเบียน "องค์กร"
# ----------------------------
class OrganizationRegistrationForm(forms.ModelForm):
    # เพิ่มฟิลด์โลโก้ (อัปโหลดได้ ไม่บังคับ)
    logo = forms.ImageField(required=False, label='โลโก้องค์กร')

    class Meta:
        model = Organization
        fields = ['name', 'address', 'business_type', 'logo']
        labels = {
            'name': 'ชื่อองค์กร',
            'address': 'ที่อยู่',
            'business_type': 'ประเภทธุรกิจ',
            'logo': 'โลโก้องค์กร',
        }
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'business_type': forms.TextInput(attrs={'placeholder': 'เช่น เทคโนโลยี, การศึกษา, การผลิต'}),
            'logo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    # (ทางเลือก) ตรวจขนาดไฟล์โลโก้ ไม่เกิน 2MB
    def clean_logo(self):
        file = self.cleaned_data.get('logo')
        if file and file.size > 2 * 1024 * 1024:
            raise forms.ValidationError('ไฟล์โลโก้ต้องมีขนาดไม่เกิน 2MB')
        return file


# ------------------------------------------
# ฟอร์ม: ผู้ใช้ที่จะเป็น "แอดมินองค์กรคนแรก"
# ------------------------------------------
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="รหัสผ่าน")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="ยืนยันรหัสผ่าน")

    # อัปโหลดรูปโปรไฟล์ (ไม่บังคับ)
    profile_image = forms.ImageField(required=False, label='รูปโปรไฟล์')

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'phone_number', 'profile_image']
        labels = {
            'username': "ชื่อผู้ใช้งาน",
            'email': "อีเมล",
            'phone_number': "หมายเลขโทรศัพท์",
            'profile_image': "รูปโปรไฟล์",
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


# ------------------------------------------------------
# ฟอร์ม: ผู้ใช้ที่ "ลงทะเบียนผ่านลิงก์" (ไม่ระบุองค์กรในฟอร์ม)
# ------------------------------------------------------
class LinkBasedUserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="รหัสผ่าน")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="ยืนยันรหัสผ่าน")

    class Meta:
        model = CustomUser
        # ไม่มีฟิลด์ organization เพราะไปผูกใน View
        fields = ['username', 'email', 'phone_number']
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
