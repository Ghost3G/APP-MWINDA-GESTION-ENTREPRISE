from django.contrib import admin

from .models import HRDocument, LeaveRequest


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status', 'leave_type')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'reason')


@admin.register(HRDocument)
class HRDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'kind', 'uploaded_by', 'created_at')
    list_filter = ('kind',)
    search_fields = ('title', 'user__username', 'user__first_name', 'user__last_name')
