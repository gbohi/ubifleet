from django.apps import AppConfig

class ParametrageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parametrage'
    verbose_name = 'Paramétrage système'

    def ready(self):
        # Applique les modifications de dotation à la clôture de leur demande
        from apps.demandes.signals import demande_cloturee
        from .dotations import appliquer_decision
        demande_cloturee.connect(appliquer_decision, dispatch_uid='parametrage_dotation')
