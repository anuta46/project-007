# borrowing/forms.py

from django import forms
from django.utils import timezone # นำเข้า timezone
from datetime import timedelta # นำเข้า timedelta
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

class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['serial_number', 'device_id', 'location', 'condition', 'status']
        labels = {
            'serial_number': "หมายเลขซีเรียล (SN)",
            'device_id': "ID อุปกรณ์",
            'location': "ตำแหน่งปัจจุบัน",
            'condition': "สภาพ",
            'status': "สถานะ",
        }
        widgets = {
            'condition': forms.TextInput(attrs={'placeholder': 'เช่น ใช้งานได้ดี, ชำรุดเล็กน้อย'}),
            'location': forms.TextInput(attrs={'placeholder': 'เช่น ห้องเก็บของ, ชั้น 3, โต๊ะทำงาน'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        serial_number = cleaned_data.get('serial_number')
        device_id = cleaned_data.get('device_id')

        if not serial_number and not device_id:
            raise forms.ValidationError("ต้องระบุหมายเลขซีเรียล (SN) หรือ ID อุปกรณ์ อย่างใดอย่างหนึ่ง")
        return cleaned_data

class LoanRequestForm(forms.ModelForm):
    # เพิ่มฟิลด์ due_date เข้ามาในฟอร์มเพื่อให้ผู้ใช้เลือกได้
    # ใช้ DateInput เพื่อให้แสดงเป็นปฏิทินในเบราว์เซอร์
    due_date = forms.DateField(
        label="วันที่คืนสิ่งของ",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="วันที่ครบกำหนดคืนสิ่งของ (ไม่เกิน 30 วันนับจากวันนี้)"
    )

    class Meta:
        model = Loan
        fields = ['reason', 'due_date'] # เพิ่ม 'due_date' เข้ามาในฟิลด์ที่ฟอร์มจะจัดการ
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
            # ตรวจสอบว่าวันที่คืนไม่ใช่วันที่ในอดีต
            if due_date < today:
                raise forms.ValidationError("วันที่ครบกำหนดคืนไม่สามารถเป็นวันที่ในอดีตได้")
            
            # ตรวจสอบว่าวันที่คืนไม่เกิน 30 วันนับจากวันนี้
            max_due_date = today + timedelta(days=30)
            if due_date > max_due_date:
                raise forms.ValidationError(f"วันที่ครบกำหนดคืนต้องไม่เกิน {max_due_date.strftime('%d/%m/%Y')} (สูงสุด 30 วัน)")
        return due_date
