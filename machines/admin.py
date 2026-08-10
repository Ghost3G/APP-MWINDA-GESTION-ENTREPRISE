from django.contrib import admin

from .models import (
    Machine,
    MachineBreakdown,
    MachineConsumable,
    MachineMaintenanceLog,
    MachinePartReplacement,
)


class BreakdownInline(admin.TabularInline):
    model = MachineBreakdown
    extra = 0


class PartInline(admin.TabularInline):
    model = MachinePartReplacement
    extra = 0


class ConsumableInline(admin.TabularInline):
    model = MachineConsumable
    extra = 0


class MaintenanceInline(admin.TabularInline):
    model = MachineMaintenanceLog
    extra = 0


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'brand',
        'model',
        'serial_number',
        'status',
        'operating_hours',
        'next_maintenance',
        'is_active',
        'photo',
    )
    list_filter = ('status', 'is_active', 'brand')
    search_fields = ('name', 'brand', 'model', 'serial_number')
    inlines = [ConsumableInline, MaintenanceInline, PartInline, BreakdownInline]


@admin.register(MachineBreakdown)
class MachineBreakdownAdmin(admin.ModelAdmin):
    list_display = ('machine', 'title', 'started_at', 'resolved_at', 'cost')
    list_filter = ('started_at',)


@admin.register(MachinePartReplacement)
class MachinePartReplacementAdmin(admin.ModelAdmin):
    list_display = ('machine', 'part_name', 'replaced_at', 'cost')


@admin.register(MachineMaintenanceLog)
class MachineMaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ('machine', 'performed_at', 'next_due', 'cost')


@admin.register(MachineConsumable)
class MachineConsumableAdmin(admin.ModelAdmin):
    list_display = ('machine', 'name', 'quantity', 'min_quantity', 'needs_replacement')
    list_filter = ('needs_replacement',)
