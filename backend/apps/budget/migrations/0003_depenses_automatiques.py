"""Interventions terminées, contrats d'assurance et sinistres reportés
dans les dépenses ; les catégories qu'ils alimentent deviennent « système »."""

from django.db import migrations


def reprendre(apps, schema_editor):
    from apps.budget import automatiques as a
    Categorie = apps.get_model('parametrage', 'CategorieDepense')
    Categorie.objects.filter(code__in=a.CATEGORIES_SYSTEME).update(systeme=True, actif=True)
    Depense = apps.get_model('budget', 'DepenseVehicule')
    sources = (
        (apps.get_model('entretien', 'Intervention'), a.REF_INTERVENTION, a.champs_intervention),
        (apps.get_model('sinistres', 'ContratAssurance'), a.REF_CONTRAT, a.champs_contrat),
        (apps.get_model('sinistres', 'Sinistre'), a.REF_SINISTRE, a.champs_sinistre),
    )
    for modele, ref, champs in sources:
        for obj in modele.objects.all():
            a.synchroniser(Depense, ref, obj, champs(obj))


def annuler(apps, schema_editor):
    from apps.budget import automatiques as a
    apps.get_model('budget', 'DepenseVehicule').objects.filter(
        ref_objet_type__in=[a.REF_INTERVENTION, a.REF_PNEU, a.REF_CONTRAT, a.REF_SINISTRE]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('budget', '0002_categorie_parametrable'),
        ('parametrage', '0009_referentiels_depenses_sinistres'),
        ('entretien', '0001_squashed'),
        ('sinistres', '0002_types_parametrables'),
    ]

    operations = [migrations.RunPython(reprendre, annuler)]
