class ExternalDBReadOnlyRouter:
    # Make sure this is exactly 'hostinger_data'
    route_app_labels = {'hostinger_data'} 

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            # Make sure this matches the dictionary key in your settings.py DATABASES
            return 'hostinger_db' 
        return None