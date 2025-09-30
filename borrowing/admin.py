# borrowing/admin.py
from django.contrib import admin
from .models import Item, Asset, Loan, ItemCategory


# ---------- ItemCategory ----------
@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon")
    search_fields = ("name", "slug", "icon")
    prepopulated_fields = {"slug": ("name",)}


# ---------- Item ----------
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    # ใช้ category แทน item_type
    list_display = ("name", "organization", "category", "total_quantity", "available_quantity", "added_at")
    search_fields = ("name", "description", "category__name", "organization__name")
    list_filter = ("organization", "category", "added_at")
    readonly_fields = ("total_quantity", "available_quantity", "added_at")


# ---------- Asset ----------
@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("item", "serial_number", "device_id", "location", "status")
    search_fields = ("item__name", "serial_number", "device_id", "location")
    list_filter = ("status", "item__organization", "item__category", "location")
    list_editable = ("location", "status")


# ---------- Loan ----------
@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("asset_display", "borrower", "reason", "borrow_date", "due_date", "return_date", "status")
    search_fields = ("asset__serial_number", "asset__device_id", "asset__item__name", "borrower__username", "reason")
    list_filter = ("status", "borrow_date", "due_date", "asset__item__organization", "asset__item__category")
    list_editable = ("status",)

    def asset_display(self, obj):
        if obj.asset.serial_number:
            return f"{obj.asset.item.name} (SN: {obj.asset.serial_number})"
        if obj.asset.device_id:
            return f"{obj.asset.item.name} (ID: {obj.asset.device_id})"
        return f"{obj.asset.item.name} (Asset {obj.asset.id})"

    asset_display.short_description = "อุปกรณ์"
