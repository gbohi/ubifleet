"""Échéances « Visite médicale » et « Contrat de travail » des chauffeurs :
seuils par défaut (30 jours attention, 7 jours urgent)."""

from django.db import migrations

SEUILS = [('visite_medicale', 'Visite médicale'), ('contrat', 'Contrat de travail')]


def creer(apps, schema_editor):
    Parametre = apps.get_model('parametrage', 'Parametre')
    for code, libelle in SEUILS:
        for niveau, jours in (('attention', 30), ('urgent', 7)):
            Parametre.objects.get_or_create(cle=f'echeance_{code}_{niveau}', defaults={
                'valeur': str(jours), 'type_valeur': 'int', 'categorie': 'alertes',
                'description': f"{libelle} : seuil « {niveau} » (jours avant expiration)"})


class Migration(migrations.Migration):

    dependencies = [('parametrage', '0011_types_document_chauffeur')]

    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
