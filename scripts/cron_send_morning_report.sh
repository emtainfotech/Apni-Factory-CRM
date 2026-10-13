#!/usr/bin/env bash
# ==============================================================================
# Apni Factory CRM — Automated WhatsApp Morning Report Cron Runner (Linux / VPS)
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment if present
if [ -f "$PROJECT_DIR/myenv/bin/activate" ]; then
    source "$PROJECT_DIR/myenv/bin/activate"
elif [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
elif [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

# Run the morning report (sends yesterday's full metrics + employee scorecard)
python manage.py send_morning_report >> "$PROJECT_DIR/whatsapp_morning_report.log" 2>&1
