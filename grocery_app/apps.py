from django.apps import AppConfig


class GroceryAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'grocery_app'

    def ready(self):
        import grocery_app.signals
