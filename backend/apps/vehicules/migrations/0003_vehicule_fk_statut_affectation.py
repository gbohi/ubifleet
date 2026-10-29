from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def reprendre_valeurs(apps, schema_editor):
    """Convertit les anciens codes texte (statut, affectation) en FK.

    Les codes des référentiels créés par parametrage.0005 reprennent
    exactement les anciennes valeurs ('en_service', 'DIRECTION', ...).
    Un code inconnu laisse la FK à NULL plutôt que de faire échouer
    la migration.
    """
    Vehicule         = apps.get_model('vehicules', 'Vehicule')
    StatutVehicule   = apps.get_model('parametrage', 'StatutVehicule')
    AffectationUsage = apps.get_model('parametrage', 'AffectationUsage')

    statuts = {s.code.strip().lower(): s for s in StatutVehicule.objects.all()}
    usages  = {a.code.strip().lower(): a for a in AffectationUsage.objects.all()}

    for v in Vehicule.objects.all():
        modifie = []

        code_statut = (v.statut_old or '').strip().lower()
        if code_statut:
            obj = statuts.get(code_statut)
            if obj is None:
                # Créer le statut manquant pour ne perdre aucune donnée
                obj = StatutVehicule.objects.create(
                    code=code_statut[:30],
                    libelle=(v.statut_old or '').strip()[:50] or code_statut,
                    couleur='gray',
                )
                statuts[code_statut] = obj
            v.statut = obj
            modifie.append('statut')

        code_usage = (v.affectation_old or '').strip().lower()
        if code_usage:
            obj = usages.get(code_usage)
            if obj is None:
                obj = AffectationUsage.objects.create(
                    code=code_usage.upper()[:30],
                    libelle=(v.affectation_old or '').strip()[:50] or code_usage,
                )
                usages[code_usage] = obj
            v.affectation = obj
            modifie.append('affectation')

        if modifie:
            v.save(update_fields=modifie)


def restaurer_valeurs(apps, schema_editor):
    """Rollback : réécrit les codes texte depuis les FK."""
    Vehicule = apps.get_model('vehicules', 'Vehicule')
    for v in Vehicule.objects.select_related('statut', 'affectation'):
        v.statut_old      = v.statut.code if v.statut else ''
        v.affectation_old = v.affectation.code if v.affectation else ''
        v.save(update_fields=['statut_old', 'affectation_old'])


class Migration(migrations.Migration):
    dependencies = [
        ('vehicules', '0002_types_documents_initiaux'),
        ('parametrage', '0005_data_initiaux'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Conserver les anciennes valeurs texte le temps de la reprise
        migrations.RenameField('vehicule', 'affectation', 'affectation_old'),
        migrations.RenameField('vehicule', 'statut', 'statut_old'),
        # Ajouter FK affectation
        migrations.AddField(
            model_name='vehicule',
            name='affectation',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vehicules',
                to='parametrage.affectationusage',
                verbose_name='Affectation / Usage'
            ),
        ),
        # Ajouter FK statut
        migrations.AddField(
            model_name='vehicule',
            name='statut',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vehicules',
                to='parametrage.statutvehicule',
                verbose_name='Statut'
            ),
        ),
        # Créer table HistoriqueStatutVehicule
        migrations.CreateModel(
            name='HistoriqueStatutVehicule',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('motif', models.CharField(blank=True, max_length=300)),
                ('date_changement', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ancien_statut', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='historiques_ancien',
                    to='parametrage.statutvehicule'
                )),
                ('nouveau_statut', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='historiques_nouveau',
                    to='parametrage.statutvehicule'
                )),
                ('vehicule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='historique_statuts',
                    to='vehicules.vehicule'
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Historique statut véhicule',
                'ordering': ['-date_changement', '-created_at'],
            },
        ),
        # Reprise des données : texte -> clé étrangère
        migrations.RunPython(reprendre_valeurs, restaurer_valeurs),
        # Les anciennes colonnes ne servent plus
        migrations.RemoveField(model_name='vehicule', name='affectation_old'),
        migrations.RemoveField(model_name='vehicule', name='statut_old'),
    ]
