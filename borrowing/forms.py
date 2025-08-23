# borrowing/forms.py

from django import forms
from .models import Item, Asset, Loan # นำเข้า Loan ด้วย

# ฟอร์มสำหรับ "ประเภทสิ่งของ" (Item)
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
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'rounded-md border border-gray-300 p-2'}),
            'item_type': forms.TextInput(attrs={'placeholder': 'เช่น อุปกรณ์อิเล็กทรอนิกส์, หนังสือ, เครื่องมือช่าง', 'class': 'rounded-md border border-gray-300 p-2'}),
        }

# ฟอร์มสำหรับ "อุปกรณ์แต่ละชิ้น" (Asset)
class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['serial_number', 'device_id', 'location', 'condition', 'status']
        labels = {
            'serial_number': "หมายเลขประจำเครื่อง (Serial Number)",
            'device_id': "รหัสอุปกรณ์ (Device ID)",
            'location': "สถานที่จัดเก็บ",
            'condition': "สภาพสิ่งของ",
            'status': "สถานะ Asset",
        }
        widgets = {
            'serial_number': forms.TextInput(attrs={'placeholder': 'เช่น SN1234567890', 'class': 'rounded-md border border-gray-300 p-2'}),
            'device_id': forms.TextInput(attrs={'placeholder': 'เช่น DEVICE-XYZ-001', 'class': 'rounded-md border border-gray-300 p-2'}),
            'location': forms.TextInput(attrs={'placeholder': 'เช่น ห้องเก็บของ A, ชั้น 3', 'class': 'rounded-md border border-gray-300 p-2'}),
            'condition': forms.Select(attrs={'class': 'rounded-md border border-gray-300 p-2'}),
            'status': forms.Select(attrs={'class': 'rounded-md border border-gray-300 p-2'}),
        }

# ฟอร์มใหม่สำหรับคำขอยืม (เฉพาะเหตุผล)
class LoanRequestForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['reason']
        labels = {
            'reason': "เหตุผลในการยืม",
        }
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'rounded-md border border-gray-300 p-2', 'placeholder': 'โปรดระบุเหตุผลในการยืมอุปกรณ์นี้ (เช่น สำหรับโปรเจกต์ X, ใช้ในการเรียน Y)'}),
        }
