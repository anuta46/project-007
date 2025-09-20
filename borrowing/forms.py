from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Item, Asset, Loan 

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'description', 'image', 'item_type']
        labels = {
            'name': "ชื่อประเภทสิ่งของ",
            'description': "รายละเอียดประเภทสิ่งของ",
            'image': "รูปภาพประเภทสิ่งของ",
            'item_type': "ประเภทกลุ่มสิ่งของ",
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'item_type': forms.TextInput(attrs={'placeholder': 'เช่น อุปกรณ์อิเล็กทรอนิกส์, หนังสือ, เครื่องมือช่าง'})
        }

# borrowing/forms.py

class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['serial_number', 'device_id', 'location', 'status']
        labels = {
            'serial_number': "หมายเลขซีเรียล (SN)",
            'device_id': "ID พัสดุและคุรุภัณฑ์",
            'location': "ตำแหน่งปัจจุบัน",
            'status': "สถานะ",
        }
        widgets = {
            'location': forms.TextInput(attrs={'placeholder': 'เช่น ห้องเก็บของ, ชั้น 3, โต๊ะทำงาน'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        # ✅ ถ้าฟอร์มนี้ถูกติ๊ก "ลบ" ให้ข้าม validation ไปได้เลย
        if cleaned_data.get('DELETE'):
            return cleaned_data

        serial_number = cleaned_data.get('serial_number')
        device_id = cleaned_data.get('device_id')

        # ✅ ฟอร์ม "ใหม่" ที่ยังว่าง (extra form) ไม่ต้องฟ้อง
        is_new_blank = (not self.instance.pk) and not serial_number and not device_id and not cleaned_data.get('location')
        if is_new_blank:
            return cleaned_data

        if not serial_number and not device_id:
            raise forms.ValidationError("ต้องระบุหมายเลขซีเรียล (SN) หรือ ID อุปกรณ์ อย่างใดอย่างหนึ่ง")

        return cleaned_data



class AssetCreateForm(forms.ModelForm):
    # กำหนดให้ field 'item' เป็น ModelChoiceField
    # เพื่อให้แสดงเป็น dropdown ของ Item
    item = forms.ModelChoiceField(
        queryset=Item.objects.all(),
        label="ประเภทสิ่งของ",
        help_text="เลือกประเภทสิ่งของที่มีอยู่แล้ว",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Asset
        # ลบ 'condition' ออกจาก fields list
        fields = ['item', 'serial_number', 'device_id', 'status', 'location']
        labels = {
            'serial_number': 'Serial Number',
            'device_id': 'Device ID',
            'status': 'สถานะ',
            'location': 'สถานที่ตั้ง',
        }
        widgets = {
            'serial_number': forms.TextInput(attrs={'placeholder': 'ไม่จำเป็น'}),
            'device_id': forms.TextInput(attrs={'placeholder': 'ไม่จำเป็น'}),
            'location': forms.TextInput(attrs={'placeholder': 'เช่น: ห้อง 101'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    # ฟังก์ชัน __init__ สำหรับ filter dropdown ให้แสดงเฉพาะ Item ขององค์กรนั้นๆ
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated and user.organization:
            self.fields['item'].queryset = Item.objects.filter(organization=user.organization)

class LoanRequestForm(forms.ModelForm):
    due_date = forms.DateField(
        label="วันที่คืนสิ่งของ",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="วันที่ครบกำหนดคืนสิ่งของ (ไม่เกิน 30 วันนับจากวันนี้)"
    )

    class Meta:
        model = Loan
        fields = ['reason', 'due_date']
        labels = {
            'reason': "เหตุผลการยืม",
        }
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4, 'placeholder': 'โปรดระบุเหตุผลในการยืมสิ่งของนี้อย่างชัดเจน เช่น ใช้สำหรับโครงการ, การเรียนการสอน'}),
        }

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date:
            today = timezone.now().date()
            if due_date < today:
                raise forms.ValidationError("วันที่ครบกำหนดคืนไม่สามารถเป็นวันที่ในอดีตได้")
            
            max_due_date = today + timedelta(days=30)
            if due_date > max_due_date:
                raise forms.ValidationError(f"วันที่ครบกำหนดคืนต้องไม่เกิน {max_due_date.strftime('%d/%m/%Y')} (สูงสุด 30 วัน)")
        return due_date
