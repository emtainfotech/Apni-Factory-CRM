from django.contrib import admin
from django.contrib import messages
from core.models import (
    Customer, WhatsAppLead, WhatsAppChat, ScheduledAppointment,
    CustomerPreference, VerifiedGST, Order, OrderItem, OrderStatusHistory,
    CompanyAssignment, TicketInternalNote, Attendance, MissedPunchOutRecord,
    Break, CallLog, CustomerActivityLog, Invoice, InvoiceItem, Transaction,
    LeaveRequest, Holiday, EmployeeProfile, ApprovedIPAddress,
    LoginApprovalRequest, LeadReassignmentRequest, WhatsAppMessageStatus,
    CandidateOnboarding, OnboardingSubmission, SellerOnboardingTracker,
    WhatsAppQuickReply, WhatsAppQuickReplyMedia, CustomerFolder, CustomerFile,
    AdminReportRecipient
)
from core.whatsapp_report_sender import send_test_report_to_number


# ==========================================
#          CUSTOMER & PREFERENCES
# ==========================================

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'first_name', 'last_name', 'phone', 'whatsapp_number',
        'email', 'customer_type', 'status', 'assigned_to', 'created_at'
    )
    list_filter = ('customer_type', 'status', 'is_gst_verified', 'created_at')
    search_fields = ('first_name', 'last_name', 'phone', 'whatsapp_number', 'email', 'company_name', 'gst_number')
    ordering = ('-created_at',)


@admin.register(CustomerPreference)
class CustomerPreferenceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'preferred_language', 'preferred_contact_method', 'marketing_email_opt_in', 'marketing_sms_opt_in')
    list_filter = ('preferred_language', 'preferred_contact_method')
    search_fields = ('customer__first_name', 'customer__last_name', 'customer__phone')


@admin.register(VerifiedGST)
class VerifiedGSTAdmin(admin.ModelAdmin):
    list_display = ('gst_number', 'verified_at')
    search_fields = ('gst_number',)
    ordering = ('-verified_at',)


@admin.register(CustomerActivityLog)
class CustomerActivityLogAdmin(admin.ModelAdmin):
    list_display = ('customer', 'employee', 'action', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('customer__first_name', 'customer__last_name', 'customer__phone', 'description')
    ordering = ('-created_at',)


@admin.register(CustomerFolder)
class CustomerFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'customer', 'parent', 'is_system_folder', 'created_by', 'created_at')
    list_filter = ('is_system_folder', 'created_at')
    search_fields = ('name', 'customer__first_name', 'customer__last_name', 'customer__phone')


@admin.register(CustomerFile)
class CustomerFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'folder', 'file_type', 'size', 'uploaded_by', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('name', 'folder__name')


@admin.register(LeadReassignmentRequest)
class LeadReassignmentRequestAdmin(admin.ModelAdmin):
    list_display = ('customer', 'requested_by', 'current_assignee', 'status', 'created_at', 'resolved_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer__first_name', 'customer__phone', 'requested_by__username', 'reason')


# ==========================================
#          ATTENDANCE & HR
# ==========================================

class BreakInline(admin.TabularInline):
    model = Break
    extra = 0
    fields = ('break_type', 'break_start', 'break_end', 'duration')
    readonly_fields = ('break_start',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'date', 'punch_in', 'punch_out', 'status',
        'is_punched_in', 'is_late', 'total_working_hours'
    )
    list_filter = ('status', 'is_late', 'is_punched_in', 'date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'ip_address')
    ordering = ('-date', '-punch_in')
    readonly_fields = ('date', 'created_at', 'updated_at')
    inlines = [BreakInline]


@admin.register(Break)
class BreakAdmin(admin.ModelAdmin):
    list_display = ('attendance', 'break_type', 'break_start', 'break_end', 'duration')
    list_filter = ('break_type',)
    ordering = ('-break_start',)
    readonly_fields = ('break_start',)


@admin.register(MissedPunchOutRecord)
class MissedPunchOutRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'missed_date', 'reported_exit_time', 'is_reviewed', 'reviewed_by', 'submitted_at')
    list_filter = ('is_reviewed', 'missed_date')
    search_fields = ('user__username', 'user__first_name', 'reason')
    ordering = ('-missed_date',)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'status', 'approved_by', 'created_at')
    list_filter = ('leave_type', 'status', 'start_date')
    search_fields = ('employee__username', 'employee__first_name', 'reason')
    ordering = ('-created_at',)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'holiday_type', 'created_by', 'created_at')
    list_filter = ('holiday_type', 'date')
    search_fields = ('name', 'description')
    ordering = ('date',)


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'dob', 'gender', 'marital_status', 'blood_group', 'salary')
    list_filter = ('gender', 'marital_status', 'blood_group')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'aadhar_number', 'pan_number')


@admin.register(ApprovedIPAddress)
class ApprovedIPAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'approved_at', 'approved_by')
    search_fields = ('user__username', 'ip_address')


@admin.register(LoginApprovalRequest)
class LoginApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'status', 'created_at', 'resolved_at', 'resolved_by')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'ip_address')


# ==========================================
#          ORDERS & INVOICES
# ==========================================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product_name', 'quantity', 'price', 'attribute', 'hsn_code')


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    fields = ('status', 'message', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'customer', 'status', 'total_amount',
        'payment_mode', 'payment_status', 'assigned_to', 'created_at'
    )
    list_filter = ('status', 'payment_status', 'payment_mode', 'created_at')
    search_fields = ('order_number', 'customer__first_name', 'customer__phone', 'lr_number', 'invoice_number')
    ordering = ('-created_at',)
    inlines = [OrderItemInline, OrderStatusHistoryInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_name', 'quantity', 'price')
    search_fields = ('product_name', 'order__order_number')


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'message', 'created_at')
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    fields = ('description', 'sac_code', 'taxable_value', 'gst_rate', 'total_amount')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_no', 'customer', 'client_name', 'invoice_date',
        'total_amount', 'payment_status', 'is_finalized', 'created_by'
    )
    list_filter = ('is_finalized', 'payment_status', 'invoice_date')
    search_fields = ('invoice_no', 'customer__first_name', 'client_name', 'client_gstin')
    ordering = ('-invoice_date', '-created_at')
    inlines = [InvoiceItemInline]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'description', 'sac_code', 'taxable_value', 'gst_rate', 'total_amount')
    search_fields = ('description', 'sac_code', 'invoice__invoice_no')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'invoice', 'amount', 'transaction_type', 'payment_method', 'transaction_date', 'created_at')
    list_filter = ('transaction_type', 'payment_method', 'transaction_date')
    search_fields = ('transaction_id', 'customer__first_name', 'customer__phone', 'remark')
    ordering = ('-transaction_date',)


# ==========================================
#          COMMUNICATION & WHATSAPP
# ==========================================

@admin.register(WhatsAppLead)
class WhatsAppLeadAdmin(admin.ModelAdmin):
    list_display = (
        'phone_number', 'customer', 'user_type', 'business_type',
        'gst_status', 'conversation_stage', 'needs_human', 'last_message_time'
    )
    list_filter = ('user_type', 'business_type', 'gst_status', 'needs_human')
    search_fields = ('phone_number', 'customer__first_name', 'customer__phone')


@admin.register(WhatsAppChat)
class WhatsAppChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'direction', 'message_snippet', 'attachment_type', 'is_read', 'timestamp')
    list_filter = ('direction', 'is_read', 'attachment_type')
    search_fields = ('message', 'customer__first_name', 'customer__phone')
    ordering = ('-timestamp',)

    def message_snippet(self, obj):
        if not obj.message:
            return '(attachment)'
        return obj.message[:50] + ('...' if len(obj.message) > 50 else '')
    message_snippet.short_description = 'Message'


class WhatsAppQuickReplyMediaInline(admin.TabularInline):
    model = WhatsAppQuickReplyMedia
    extra = 0
    fields = ('file_name', 'media_type', 'file', 'file_size', 'order')


@admin.register(WhatsAppQuickReply)
class WhatsAppQuickReplyAdmin(admin.ModelAdmin):
    list_display = ('title', 'keyword', 'content_type', 'is_active', 'created_by', 'created_at')
    list_filter = ('content_type', 'is_active')
    search_fields = ('title', 'keyword', 'message')
    inlines = [WhatsAppQuickReplyMediaInline]


@admin.register(WhatsAppQuickReplyMedia)
class WhatsAppQuickReplyMediaAdmin(admin.ModelAdmin):
    list_display = ('quick_reply', 'file_name', 'media_type', 'file_size', 'order')
    list_filter = ('media_type',)


@admin.register(WhatsAppMessageStatus)
class WhatsAppMessageStatusAdmin(admin.ModelAdmin):
    list_display = ('wamid', 'recipient_id', 'status', 'error_code', 'timestamp', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('wamid', 'recipient_id', 'error_code', 'error_title')
    ordering = ('-created_at',)


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ('customer', 'employee', 'call_status', 'follow_up_date', 'call_duration', 'created_at')
    list_filter = ('call_status', 'created_at')
    search_fields = ('customer__first_name', 'customer__phone', 'employee__username', 'remark')
    ordering = ('-created_at',)


@admin.register(ScheduledAppointment)
class ScheduledAppointmentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'time_slot', 'status', 'created_at')
    list_filter = ('status', 'time_slot')
    search_fields = ('customer__first_name', 'customer__phone')
    ordering = ('-created_at',)


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


# ==========================================
#          ONBOARDING & OPERATIONS
# ==========================================

@admin.register(CandidateOnboarding)
class CandidateOnboardingAdmin(admin.ModelAdmin):
    list_display = ('candidate_name', 'mobile', 'email', 'experience_type', 'status', 'created_at')
    list_filter = ('status', 'experience_type', 'created_at')
    search_fields = ('candidate_name', 'mobile', 'email', 'reporting_manager')
    ordering = ('-created_at',)


@admin.register(OnboardingSubmission)
class OnboardingSubmissionAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'candidate', 'personal_mobile', 'personal_email', 'submitted_at')
    search_fields = ('full_name', 'personal_mobile', 'personal_email', 'pan_number', 'aadhar_number')
    ordering = ('-submitted_at',)


@admin.register(SellerOnboardingTracker)
class SellerOnboardingTrackerAdmin(admin.ModelAdmin):
    list_display = (
        'hostinger_user_id', 'onboarding_status', 'catalogue_status',
        'welcome_whatsapp_sent', 'welcome_email_sent', 'assigned_to', 'updated_at'
    )
    list_filter = ('onboarding_status', 'catalogue_status', 'welcome_whatsapp_sent', 'welcome_email_sent')
    search_fields = ('hostinger_user_id', 'assigned_to__username')
    ordering = ('-updated_at',)


@admin.register(CompanyAssignment)
class CompanyAssignmentAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'company_id', 'assigned_to', 'last_sync', 'created_at')
    list_filter = ('assigned_to',)
    search_fields = ('company_name', 'company_id')


@admin.register(TicketInternalNote)
class TicketInternalNoteAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'created_by', 'note_snippet', 'created_at')
    search_fields = ('ticket_id', 'note')
    ordering = ('-created_at',)

    def note_snippet(self, obj):
        if not obj.note:
            return '-'
        return obj.note[:60] + ('...' if len(obj.note) > 60 else '')
    note_snippet.short_description = 'Note'