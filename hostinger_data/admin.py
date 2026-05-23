from django.contrib import admin
from django.apps import apps

# Get all models from the current app ('hostinger_data')
app_models = apps.get_app_config('hostinger_data').get_models()

# Loop through and register them all automatically
for model in app_models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        # This prevents errors if you explicitly register a model below
        pass