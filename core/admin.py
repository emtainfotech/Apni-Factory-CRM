from django.contrib import admin
from django.contrib import messages
from core.models import Customer, WhatsAppMessageStatus, AdminReportRecipient, Holiday
from core.whatsapp_report_sender import send_test_report_to_number


@admin.register(AdminReportRecipient)
class AdminReportRecipientAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'phone', 'report_type',
        'include_employee_detail', 'allow_commands',
        'is_active', 'created_at',
    )
    list_filter = ('report_type', 'is_active', 'allow_commands', 'include_employee_detail')
    search_fields = ('name', 'phone')
    actions = ['send_test_morning_report', 'send_test_today_report', 'send_test_overall_report']

    @admin.action(description="Send Test Morning Report (Yesterday) via WhatsApp")
    def send_test_morning_report(self, request, queryset):
        success_count = 0
        for recipient in queryset:
            ok, err = send_test_report_to_number(recipient.phone, report_type='yesterday')
            if ok:
                success_count += 1
            else:
                self.message_user(request, f"Failed for {recipient.phone}: {err}", level=messages.ERROR)
        if success_count:
            self.message_user(request, f"Successfully sent morning test report to {success_count} recipient(s).", level=messages.SUCCESS)

    @admin.action(description="Send Test Today Report (Live) via WhatsApp")
    def send_test_today_report(self, request, queryset):
        success_count = 0
        for recipient in queryset:
            ok, err = send_test_report_to_number(recipient.phone, report_type='today')
            if ok:
                success_count += 1
            else:
                self.message_user(request, f"Failed for {recipient.phone}: {err}", level=messages.ERROR)
        if success_count:
            self.message_user(request, f"Successfully sent today's test report to {success_count} recipient(s).", level=messages.SUCCESS)

    @admin.action(description="Send Test Overall Report (All-Time) via WhatsApp")
    def send_test_overall_report(self, request, queryset):
        success_count = 0
        for recipient in queryset:
            ok, err = send_test_report_to_number(recipient.phone, report_type='overall')
            if ok:
                success_count += 1
            else:
                self.message_user(request, f"Failed for {recipient.phone}: {err}", level=messages.ERROR)
        if success_count:
            self.message_user(request, f"Successfully sent overall test report to {success_count} recipient(s).", level=messages.SUCCESS)


admin.site.register(Customer)
admin.site.register(WhatsAppMessageStatus)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'holiday_type', 'created_by', 'created_at')
    list_filter = ('holiday_type', 'date')
    search_fields = ('name', 'description')
    ordering = ('date',)