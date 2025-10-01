# borrowing/forms.py
from django import forms
from django.utils import timezone
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Item, Asset, Loan, ItemCategory


# ───────────────────────── Item / Category ─────────────────────────

class ItemCategoryForm(forms.ModelForm):
    class Meta:
        model = ItemCategory
        fields = ['name', 'icon']   # ให้แน่ใจว่ามี icon
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['icon'].required = False
        self.fields['icon'].help_text = "เช่น fa-laptop, fa-tag (เว้นว่างได้)"


# borrowing/forms.py
from django import forms
from .models import Item, ItemCategory

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'description', 'image', 'category']
        labels = {
            'name': "ชื่อพัสดุ/คุรุภัณฑ์",
            'description': "รายละเอียดพัสดุ/คุรุภัณฑ์",
            'image': "รูปภาพพัสดุ/คุรุภัณฑ์",
            'category': "หมวดพัสดุ/คุรุภัณฑ์",
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # เรียงหมวดตามชื่อ
        self.fields['category'].queryset = ItemCategory.objects.order_by('name')
        # เปลี่ยน label ของแต่ละตัวเลือกให้โชว์ "ไอคอน ชื่อ" (หรือเฉพาะชื่อถ้าไม่มีไอคอน)
        self.fields['category'].label_from_instance = (
            lambda obj: f"{obj.icon} {obj.name}".strip() if obj.icon else obj.name
        )



# ───────────────────────── Asset ─────────────────────────

class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['serial_number', 'device_id', 'location', 'status']
        labels = {
            'serial_number': "หมายเลขซีเรียล (SN)",
            'device_id': "ID อุปกรณ์/ครุภัณฑ์",
            'location': "ตำแหน่งปัจจุบัน",
            'status': "สถานะ",
        }
        widgets = {
            'location': forms.TextInput(attrs={'placeholder': 'เช่น ห้องเก็บของ, ชั้น 3, โต๊ะทำงาน'}),
        }

    def clean(self):
        cleaned = super().clean()

        # รองรับกรณีใช้งานใน inline formset (ถ้าติ๊กลบ ให้ข้าม validation อื่น ๆ)
        if cleaned.get('DELETE'):
            return cleaned

        sn = (cleaned.get('serial_number') or '').strip()
        did = (cleaned.get('device_id') or '').strip()

        # ฟอร์มใหม่ที่ยังว่าง (extra form) ไม่ต้องฟ้อง error
        is_new_blank = (not self.instance.pk) and not sn and not did and not (cleaned.get('location') or '').strip()
        if is_new_blank:
            return cleaned

        if not sn and not did:
            raise forms.ValidationError("ต้องระบุอย่างน้อย 1 ช่อง ระหว่าง Serial Number หรือ Device ID")
        return cleaned


class AssetCreateForm(forms.ModelForm):
    """ใช้สร้าง Asset ทีละชิ้น (นอกหน้า inline)"""
    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        label="ประเภทสิ่งของ",
        help_text="เลือกประเภทสิ่งของที่มีอยู่แล้ว",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Asset
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

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and getattr(user, 'organization_id', None):
            self.fields['item'].queryset = Item.objects.filter(
                organization=user.organization
            ).order_by('name')
        else:
            self.fields['item'].queryset = Item.objects.none()

    def clean(self):
        cleaned = super().clean()
        sn = (cleaned.get('serial_number') or '').strip()
        did = (cleaned.get('device_id') or '').strip()
        if not sn and not did:
            raise forms.ValidationError('กรุณาระบุ Serial Number หรือ Device ID อย่างน้อยหนึ่งอย่าง')
        return cleaned


# ───────────── Inline Formset: เพิ่มอุปกรณ์หลายชิ้นในหน้าเดียว ─────────────

class _AssetInlineFormSet(BaseInlineFormSet):
    """
    - บังคับให้มีอย่างน้อย 1 ชิ้น (ที่ไม่ถูกติ๊กลบ)
    - กัน SN/DeviceID ซ้ำกันในชุดเดียวกันก่อนชน DB unique
    - ปล่อยฟอร์ม extra ที่ว่างจริง ๆ โดยไม่มี error
    """
    def clean(self):
        super().clean()

        valid_forms = []
        seen_sn = set()
        seen_did = set()
        errors = []

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            cd = form.cleaned_data

            # ข้ามถ้าติ๊กลบ
            if cd.get('DELETE'):
                continue

            sn = (cd.get('serial_number') or '').strip()
            did = (cd.get('device_id') or '').strip()
            loc = (cd.get('location') or '').strip()

            # ข้าม extra ที่ว่างจริง ๆ
            if not form.instance.pk and not sn and not did and not loc:
                continue

            # ต้องมี SN หรือ DID อย่างน้อยหนึ่ง
            if not sn and not did:
                form.add_error(None, "กรุณากรอก Serial Number หรือ Device ID อย่างน้อยหนึ่งอย่าง")
                errors.append(form)
            else:
                # กันซ้ำภายใน formset เดียวกัน
                if sn:
                    if sn in seen_sn:
                        form.add_error('serial_number', "หมายเลขซีเรียลซ้ำกับรายการอื่นในชุดนี้")
                        errors.append(form)
                    seen_sn.add(sn)
                if did:
                    if did in seen_did:
                        form.add_error('device_id', "Device ID ซ้ำกับรายการอื่นในชุดนี้")
                        errors.append(form)
                    seen_did.add(did)

            valid_forms.append(form)

        if len(valid_forms) == 0:
            raise forms.ValidationError("กรุณาเพิ่มอุปกรณ์อย่างน้อย 1 ชิ้น")

        # รวม error ถ้ามี
        if errors:
            raise forms.ValidationError("กรุณาแก้ไขข้อผิดพลาดของอุปกรณ์ในรายการ")


AssetFormSet = inlineformset_factory(
    parent_model=Item,
    model=Asset,
    form=AssetForm,
    formset=_AssetInlineFormSet,
    fields=['serial_number', 'device_id', 'location', 'status'],
    extra=1,          # เริ่มด้วย 1 ฟอร์มว่าง
    can_delete=True,  # ให้ติ๊กลบได้
    validate_min=True,
)


# ───────────────────────── Loan ─────────────────────────

class LoanRequestForm(forms.ModelForm):
    start_date = forms.DateField(
        label="วันที่เริ่มยืม (นัดรับ)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="เลือกวันที่จะมารับอุปกรณ์ (วันนี้หรืออนาคตก็ได้)"
    )
    due_date = forms.DateField(
        label="วันที่คืนสิ่งของ",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="วันที่ครบกำหนดคืน (ไม่เกิน 30 วันนับจากวันเริ่มยืม)"
    )

    class Meta:
        model = Loan
        fields = ['reason', 'start_date', 'due_date']
        labels = {
            'reason': "เหตุผลการยืม",
        }
        widgets = {
            'reason': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'โปรดระบุเหตุผล เช่น ใช้สำหรับโครงการ/การเรียนการสอน'
            })
        }

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        due_date = cleaned.get('due_date')

        # ถ้ายังไม่กรอกครบทั้งคู่ ปล่อยให้ field-level validation จัดการ
        if not start_date or not due_date:
            return cleaned

        today = timezone.now().date()

        # วันเริ่มต้องเป็นวันนี้หรืออนาคต
        if start_date < today:
            self.add_error('start_date', "วันเริ่มยืมต้องเป็นวันนี้หรืออนาคต")

        # กำหนดคืนต้อง > เริ่มยืม อย่างน้อย 1 วัน
        if due_date <= start_date:
            self.add_error('due_date', "วันครบกำหนดต้องหลังวันเริ่มยืมอย่างน้อย 1 วัน")

        # จำกัดสูงสุด 30 วัน
        if (due_date - start_date).days > 30:
            self.add_error('due_date', "ระยะเวลายืมต้องไม่เกิน 30 วัน")

        return cleaned
