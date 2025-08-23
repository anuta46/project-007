# borrowing/admin.py
from django.contrib import admin
from .models import Item, Asset, Loan # นำเข้าโมเดล Item, Asset, และ Loan

# ลงทะเบียนโมเดล Item (ตอนนี้คือ "ประเภทสิ่งของ")
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    # กำหนดฟิลด์ที่จะแสดงในหน้ารายการ "ประเภทสิ่งของ" ใน Admin
    list_display = ('name', 'organization', 'item_type', 'total_quantity', 'available_quantity', 'added_at')
    # เพิ่มฟิลด์ที่สามารถใช้ค้นหาได้
    search_fields = ('name', 'description', 'item_type')
    # เพิ่มฟิลด์ที่สามารถใช้กรองได้
    list_filter = ('organization', 'item_type', 'added_at')
    # ฟิลด์ที่อ่านอย่างเดียว (ถูกคำนวณจาก Assets)
    readonly_fields = ('total_quantity', 'available_quantity', 'added_at')

# ลงทะเบียนโมเดล Asset (อุปกรณ์แต่ละชิ้น)
@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    # กำหนดฟิลด์ที่จะแสดงในหน้ารายการ "อุปกรณ์แต่ละชิ้น" ใน Admin
    list_display = ('item', 'serial_number', 'device_id', 'location', 'condition', 'status')
    # เพิ่มฟิลด์ที่สามารถใช้ค้นหาได้
    search_fields = ('item__name', 'serial_number', 'device_id', 'location') # ค้นหาจากชื่อประเภทสิ่งของและฟิลด์ของ Asset
    # เพิ่มฟิลด์ที่สามารถใช้กรองได้
    list_filter = ('item__organization', 'item__item_type', 'location', 'condition', 'status') # กรองจาก Item และ Asset
    # ฟิลด์ที่แก้ไขได้โดยตรงจากหน้ารายการ (list_editable)
    list_editable = ('location', 'condition', 'status')

# ลงทะเบียนโมเดล Loan (รายการยืม)
@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    # เปลี่ยน 'item' เป็น 'asset' และปรับการแสดงผล
    list_display = ('asset_display', 'borrower', 'reason', 'borrow_date', 'due_date', 'return_date', 'status') # เพิ่ม 'reason'
    # ปรับ search_fields ให้ค้นหาจาก Asset และ Item
    search_fields = ('asset__serial_number', 'asset__device_id', 'asset__item__name', 'borrower__username', 'reason') # เพิ่ม 'reason'
    list_filter = ('status', 'borrow_date', 'due_date', 'asset__item__organization') # กรองตามองค์กรของ Asset
    list_editable = ('status',)

    # เพิ่ม method สำหรับแสดงชื่อ Asset ใน list_display
    def asset_display(self, obj):
        if obj.asset.serial_number:
            return f"{obj.asset.item.name} (SN: {obj.asset.serial_number})"
        elif obj.asset.device_id:
            return f"{obj.asset.item.name} (ID: {obj.asset.device_id})"
        return f"{obj.asset.item.name} (Asset {obj.asset.id})"
    asset_display.short_description = 'อุปกรณ์' # ตั้งชื่อคอลัมน์
