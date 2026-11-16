from django.contrib import admin

from .models import (
    DisciplinaryAction,
    HRDocument,
    JobApplication,
    LeaveRequest,
    PerformanceReview,
    TrainingRecord,
)


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


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'position', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('full_name', 'position', 'email', 'phone')


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'review_date', 'rating', 'reviewer')
    list_filter = ('rating',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')


@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'status', 'start_date', 'end_date')
    list_filter = ('status',)
    search_fields = ('title', 'user__username', 'provider')


@admin.register(DisciplinaryAction)
class DisciplinaryActionAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'action_date', 'recorded_by')
    list_filter = ('kind',)
    search_fields = ('user__username', 'reason', 'decision')
