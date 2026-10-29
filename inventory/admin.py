from django.contrib import admin

from .models import DeliveryShipment, PurchaseRequest, StockItem, StockMovement, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialty', 'city', 'phone', 'is_active')
    list_filter = ('specialty', 'is_active')
    search_fields = ('name', 'phone', 'email', 'city', 'contact_name')


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


@admin.register(DeliveryShipment)
class DeliveryShipmentAdmin(admin.ModelAdmin):
    list_display = ('project', 'status', 'scheduled_date', 'driver_name', 'delivered_at')
    list_filter = ('status',)
    search_fields = ('project__name', 'driver_name', 'recipient_name', 'destination')
