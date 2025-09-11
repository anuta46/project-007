# borrowing/admin.py
from django.contrib import admin
from .models import Item, Asset, Loan # นำเข้าโมเดล Item, Asset, และ Loan

# ลงทะเบียนโมเดล Item (ตอนนี้คือ "ประเภทสิ่งของ")
@admin.register(Item) # ใช้ @admin.register decorator เพื่อลงทะเบียนโมเดลกับ Admin
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'item_type', 'total_quantity', 'available_quantity', 'added_at')
    search_fields = ('name', 'description', 'item_type')
    # list_filter = ('organization', 'item_type', 'added_at')
    readonly_fields = ('total_quantity', 'available_quantity', 'added_at') # กำหนดฟิวด์ให้อแก้ไขไม่ได้

# ลงทะเบียนโมเดล Asset (อุปกรณ์แต่ละชิ้น)
@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    # แก้ไข: ลบ 'condition' ออกจาก list_display
    list_display = ('item', 'serial_number', 'device_id', 'location', 'status')
    search_fields = ('item__name', 'serial_number', 'device_id', 'location')
    # list_filter = ('item__organization', 'item__item_type', 'location', 'condition', 'status')
    # แก้ไข: ลบ 'condition' ออกจาก list_editable
    list_editable = ('location', 'status')

# ลงทะเบียนโมเดล Loan (รายการยืม)
@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('asset_display', 'borrower', 'reason', 'borrow_date', 'due_date', 'return_date', 'status')
    search_fields = ('asset__serial_number', 'asset__device_id', 'asset__item__name', 'borrower__username', 'reason')
    # list_filter = ('status', 'borrow_date', 'due_date', 'asset__item__organization')
    list_editable = ('status',)

    def asset_display(self, obj):
        if obj.asset.serial_number:
            return f"{obj.asset.item.name} (SN: {obj.asset.serial_number})"
        elif obj.asset.device_id:
            return f"{obj.asset.item.name} (ID: {obj.asset.device_id})"
        return f"{obj.asset.item.name} (Asset {obj.asset.id})"
    asset_display.short_description = 'อุปกรณ์'
