"""
send_morning_report.py — Apni Factory CRM Management Command
============================================================
Dispatches WhatsApp dashboard reports to configured admin numbers.
Can be run via cron / Windows Task Scheduler / command line.

Examples:
    # Send morning report (yesterday's stats) to all active morning recipients:
    python manage.py send_morning_report

    # Send today's report to a specific number:
    python manage.py send_morning_report --phone 9340547135 --type today

    # Preview report in console without sending:
    python manage.py send_morning_report --dry-run
"""

from django.core.management.base import BaseCommand
from core.models import AdminReportRecipient
from core.report_builder import (
    get_today_report,
    get_yesterday_report,
    get_overall_report,
    get_week_report,
    get_month_report,
)
from core.whatsapp_report_sender import (
    send_morning_reports,
    send_evening_reports,
    send_whatsapp_chunks,
)


class Command(BaseCommand):
    help = "Dispatches automated dashboard report to admin WhatsApp recipients."

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='morning',
            choices=['morning', 'evening', 'today', 'yesterday', 'overall', 'week', 'month'],
            help="Type of report to send (default: morning, which sends yesterday's metrics)"
        )
        parser.add_argument(
            '--phone',
            type=str,
            default=None,
            help="Specific recipient phone number (bypasses database recipients if specified)"
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Print generated report text to stdout without sending via WhatsApp"
        )

    def handle(self, *args, **options):
        report_type = options['type']
        target_phone = options['phone']
        dry_run = options['dry_run']

        self.stdout.write(self.style.NOTICE(f"=== Admin WhatsApp Report Dispatcher (Type: {report_type}) ==="))

        # Determine report text
        if report_type in ['morning', 'today', 'evening']:
            report_text = get_today_report()
        elif report_type == 'yesterday':
            report_text = get_yesterday_report()
        elif report_type == 'overall':
            report_text = get_overall_report()
        elif report_type == 'week':
            report_text = get_week_report()
        elif report_type == 'month':
            report_text = get_month_report()
        else:
            report_text = get_today_report()

        if dry_run:
            self.stdout.write(self.style.SUCCESS("--- DRY RUN REPORT PREVIEW ---"))
            try:
                self.stdout.write(report_text)
            except UnicodeEncodeError:
                import sys
                enc = sys.stdout.encoding or 'utf-8'
                safe_text = report_text.encode(enc, errors='replace').decode(enc)
                self.stdout.write(safe_text)
            self.stdout.write(self.style.SUCCESS("--- END PREVIEW (No WhatsApp message sent) ---"))
            return

        # If specific phone provided
        if target_phone:
            self.stdout.write(f"Sending {report_type} report directly to: {target_phone}...")
            ok, err = send_whatsapp_chunks(target_phone, report_text)
            if ok:
                self.stdout.write(self.style.SUCCESS(f"Successfully sent report to {target_phone}!"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed sending to {target_phone}: {err}"))
            return

        # Batch dispatch
        if report_type == 'evening':
            res = send_evening_reports()
        else:
            res = send_morning_reports()

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed! Total: {res.get('count', 0)}, Success: {res.get('success', 0)}, Failed: {res.get('failed', 0)}"
            )
        )
        for detail in res.get('details', []):
            status = detail.get('status')
            if status == 'sent':
                self.stdout.write(f"  [OK] {detail.get('name')} ({detail.get('phone')})")
            else:
                self.stdout.write(self.style.WARNING(f"  [FAIL] {detail.get('name')} ({detail.get('phone')}): {detail.get('error')}"))
