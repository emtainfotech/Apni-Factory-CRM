from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        import os
        import shutil
        from django.conf import settings

        try:
            pdf_filename = 'Apni_Factory_Seller_Onboarding_Guide_Final.pdf'
            src_candidates = [
                os.path.join(settings.BASE_DIR, pdf_filename),
                os.path.join(settings.BASE_DIR, 'core', 'static', 'documents', pdf_filename),
            ]
            valid_src = next((s for s in src_candidates if os.path.exists(s)), None)
            if valid_src:
                target_dirs = [
                    os.path.join(settings.MEDIA_ROOT, 'documents'),
                    os.path.join(settings.MEDIA_ROOT, 'whatsapp_attachments'),
                ]
                for td in target_dirs:
                    os.makedirs(td, exist_ok=True)
                    target_file = os.path.join(td, pdf_filename)
                    if not os.path.exists(target_file):
                        shutil.copyfile(valid_src, target_file)
        except Exception:
            pass
