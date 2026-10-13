#!/usr/bin/env bash
# ==============================================================================
# Apni Factory CRM — Automated WhatsApp Evening Report Cron Runner (8:00 PM)
# Server Path: /var/www/apnifactory-crm
# ==============================================================================

# Project directory on server
if [ -d "/var/www/apnifactory-crm" ]; then
    PROJECT_DIR="/var/www/apnifactory-crm"
else
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
if [ -f "$PROJECT_DIR/myenv/bin/activate" ]; then
    source "$PROJECT_DIR/myenv/bin/activate"
elif [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
elif [ -f "myenv/bin/activate" ]; then
    source "myenv/bin/activate"
fi

# Run evening report (sends today's end-of-day summary to active evening/both recipients)
python manage.py send_morning_report --type evening >> "$PROJECT_DIR/whatsapp_evening_report.log" 2>&1
