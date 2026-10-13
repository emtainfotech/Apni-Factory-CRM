"""
core/tasks.py — Apni Factory CRM
=================================
Celery background tasks for scheduled dashboard reports and automation.
"""

import logging
from celery import shared_task
from core.whatsapp_report_sender import (
    send_morning_reports,
    send_evening_reports,
    send_test_report_to_number,
)

logger = logging.getLogger(__name__)


@shared_task(name="core.tasks.send_morning_dashboard_report")
def send_morning_dashboard_report():
    """
    Scheduled task that fires daily at 6:00 AM IST.
    Sends yesterday's complete dashboard & employee scorecard to all
    registered admin WhatsApp recipients.
    """
    logger.info("Executing Celery task: send_morning_dashboard_report")
    try:
        result = send_morning_reports()
        logger.info(f"Morning report task completed: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error executing send_morning_dashboard_report: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name="core.tasks.send_evening_dashboard_report")
def send_evening_dashboard_report():
    """
    Scheduled task that fires daily at 8:00 PM IST.
    Sends today's real-time figures & employee performance summary.
    """
    logger.info("Executing Celery task: send_evening_dashboard_report")
    try:
        result = send_evening_reports()
        logger.info(f"Evening report task completed: {result}")
        return result
    except Exception as e:
        logger.exception(f"Error executing send_evening_dashboard_report: {e}")
        return {'status': 'error', 'error': str(e)}


@shared_task(name="core.tasks.send_test_report_async")
def send_test_report_async(phone: str, report_type: str = "yesterday"):
    """
    Asynchronously sends a test report triggered from CRM UI.
    """
    logger.info(f"Sending test report to {phone} (type: {report_type})")
    try:
        ok, err = send_test_report_to_number(phone, report_type)
        return {'success': ok, 'error': err}
    except Exception as e:
        logger.exception(f"Error sending test report to {phone}: {e}")
        return {'success': False, 'error': str(e)}
