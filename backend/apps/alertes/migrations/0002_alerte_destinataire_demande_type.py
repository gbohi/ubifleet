"""Ajout du champ destinataire et du type DEMANDE_A_VALIDER dans Alerte."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('alertes', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='alerte',
            name='destinataire',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='alertes_recues',
                to=settings.AUTH_USER_MODEL,
                help_text="Utilisateur destinataire de l'alerte"
            ),
        ),
        migrations.AlterField(
            model_name='alerte',
            name='type_alerte',
            field=models.CharField(
                max_length=25,
                choices=[
                    ('revision_due', 'Révision due'),
                    ('assurance_exp', 'Assurance expirant bientôt'),
                    ('assurance_expiree', 'Assurance expirée'),
                    ('conso_anormale', 'Consommation anormale'),
                    ('ct_exp', 'Contrôle technique expirant'),
                    ('ct_expiree', 'Contrôle technique expiré'),
                    ('permis_exp', 'Permis expirant bientôt'),
                    ('permis_expire', 'Permis expiré'),
                    ('budget_depasse', 'Budget dépassé'),
                    ('pneu_usure', 'Pneu à changer'),
                    ('plein_anomalie', 'Anomalie plein carburant'),
                    ('sinistre_ouvert', 'Sinistre en attente de traitement'),
                    ('demande_a_valider', 'Demande à valider'),
                ]
            ),
        ),
    ]
