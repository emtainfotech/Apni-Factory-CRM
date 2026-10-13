@echo off
:: ==============================================================================
:: Apni Factory CRM — Automated WhatsApp Morning Report Runner (Windows)
:: ==============================================================================

cd /d "e:\APNI FACTORY\ApniFactoryCRM"

:: Use the virtual environment Python if exists, otherwise fallback to system Python
if exist "e:\APNI FACTORY\ApniFactoryCRM\myenv\Scripts\python.exe" (
    "e:\APNI FACTORY\ApniFactoryCRM\myenv\Scripts\python.exe" manage.py send_morning_report >> "e:\APNI FACTORY\ApniFactoryCRM\whatsapp_morning_report.log" 2>&1
) else (
    python manage.py send_morning_report >> "e:\APNI FACTORY\ApniFactoryCRM\whatsapp_morning_report.log" 2>&1
)
