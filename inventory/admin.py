from django.contrib import admin

from .models import PurchaseRequest, StockItem, StockMovement, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'is_active')
    search_fields = ('name', 'phone', 'email')


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'min_stock', 'max_stock', 'unit', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'sku')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'movement_type', 'quantity', 'balance_after', 'created_by', 'created_at')
    list_filter = ('movement_type',)


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('item', 'quantity', 'status', 'auto_generated', 'created_at')
    list_filter = ('status', 'auto_generated')
