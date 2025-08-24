# borrowing/forms.py

from django import forms
from .models import Item, Asset, Loan # นำเข้า Asset และ Loan

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        # ลบ quantity ออกไป เนื่องจากจะถูกคำนวณจาก Assets
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
    class Meta:
        model = Loan
        fields = ['reason'] # มีเพียงฟิลด์ 'reason' สำหรับผู้ใช้ในการกรอก
        labels = {
            'reason': "เหตุผลการยืม",
        }
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4, 'placeholder': 'โปรดระบุเหตุผลในการยืมสิ่งของนี้อย่างชัดเจน เช่น ใช้สำหรับโครงการ, การเรียนการสอน'}),
        }
