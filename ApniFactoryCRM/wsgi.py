"""
WSGI config for ApniFactoryCRM project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from django.core.wsgi import get_wsgi_application

# Add the project directory to the sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Explicitly load .env file for Apache/mod_wsgi
load_dotenv(os.path.join(BASE_DIR, '.env'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ApniFactoryCRM.settings')

application = get_wsgi_application()
