"""
UbiFleet — Moteur d'importation du fichier Total (CSV/Excel)
Gère : détection encodage, séparateur, mapping colonnes, doublons, erreurs
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Tuple

# Mapping exact : nom colonne fichier → champ modèle
COLUMN_MAP = {
    'Numéro de la filiale':                     'numero_filiale',
    'Nom de la filiale':                        'nom_filiale',
    'No. du client':                            'numero_client',
    'Nom du client':                            'nom_client',
    'Numéro du moyen de paiement':              'numero_moyen_paiement',
    'Nom du titulaire du mode de paiement':     'nom_titulaire_paiement',
    'Numéro de chauffeur':                      'numero_chauffeur',
    'Nom de chauffeur':                         'nom_chauffeur',
    "Plaque d'immatriculation":                 'immatriculation',
    'Kilométrage précédent':                    'kilometrage_precedent',
    'Kilométrage actuelle':                     'kilometrage_actuel',
    'Date de transaction':                      'date_transaction',
    'Heure de la transaction':                  'heure_transaction',
    'Numéro de ticket':                         'numero_ticket',
    'Numéro de la station':                     'numero_station',
    'Nom de la station':                        'nom_station',
    'Numéro de terminal':                       'numero_terminal',
    'Nom de pompiste':                          'nom_pompiste',
    'Type de transaction':                      'type_transaction',
    'Nom de transaction':                       'nom_transaction',
    'Montant Pré-autorisé':                     'montant_preautorise',
    'Solde avant':                              'solde_avant',
    'Nom de produit':                           'nom_produit',
    'Prix unitaire':                            'prix_unitaire',
    'Volume':                                   'volume',
    'Montant':                                  'montant',
    'Solde après':                              'solde_apres',
    'Bonus MyPass utilisé':                     'bonus_mypass_utilise',
    'Bonus MyPass après la transaction':        'bonus_mypass_apres',
    'Chrone de la SAM':                         'chrone_sam',
    'ATC':                                      'atc',
    'Profil de transaction':                    'profil_transaction',
    "Valeur précédente du compteur d'heures":   'compteur_heures_precedent',
    "Valeur actuelle du compteur d'heures":     'compteur_heures_actuel',
    'Nom de service':                           'nom_service',
    "Code d'autorisation":                      'code_autorisation',
    'Statut de transaction':                    'statut_transaction',
}

DECIMAL_FIELDS = {
    'kilometrage_precedent', 'kilometrage_actuel',
    'montant_preautorise', 'solde_avant', 'prix_unitaire', 'volume',
    'montant', 'solde_apres', 'bonus_mypass_utilise', 'bonus_mypass_apres',
    'compteur_heures_precedent', 'compteur_heures_actuel',
}


def _parse_decimal(value: str):
    """Convertit '1 234,56' ou '1234.56' en Decimal."""
    if not value or value.strip() in ('', '-', 'N/A'):
        return None
    try:
        cleaned = value.strip().replace(' ', '').replace(',', '.')
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(value: str):
    """Parse '01/01/2026' en date."""
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _parse_time(value: str):
    """Parse '00:39' en time."""
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(value.strip(), fmt).time()
        except (ValueError, AttributeError):
            continue
    return None


def _detect_delimiter(content: str) -> str:
    """Détecte le séparateur ; ou ,"""
    first_line = content.split('\n')[0]
    return ';' if first_line.count(';') > first_line.count(',') else ','


def importer_fichier(
    fichier_bytes: bytes,
    import_source,
    encoding='utf-8-sig'
) -> Dict:
    """
    Importe un fichier CSV/Excel Total.
    Retourne : { importees, doublons, erreurs, lignes_erreur }
    """
    from .models import TransactionCarburant

    # Décoder le contenu
    try:
        content = fichier_bytes.decode(encoding)
    except UnicodeDecodeError:
        content = fichier_bytes.decode('latin-1')

    delimiter = _detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

    importees = 0
    doublons  = 0
    erreurs   = 0
    lignes_erreur = []

    # Construire l'ensemble des clés existantes pour éviter N requêtes
    existing_keys = set(
        TransactionCarburant.objects.values_list(
            'numero_ticket', 'code_autorisation', 'date_transaction'
        )
    )

    for line_num, row in enumerate(reader, start=2):
        try:
            data = {'import_source': import_source}

            for col_fichier, field_name in COLUMN_MAP.items():
                # Chercher avec et sans espaces superflus
                raw = row.get(col_fichier, row.get(col_fichier.strip(), '')).strip()

                if field_name == 'date_transaction':
                    data[field_name] = _parse_date(raw)
                elif field_name == 'heure_transaction':
                    data[field_name] = _parse_time(raw)
                elif field_name in DECIMAL_FIELDS:
                    data[field_name] = _parse_decimal(raw)
                else:
                    data[field_name] = raw

            # Clé d'unicité
            key = (
                str(data.get('numero_ticket', '')),
                str(data.get('code_autorisation', '')),
                data.get('date_transaction'),
            )

            if key in existing_keys:
                doublons += 1
                continue

            TransactionCarburant.objects.create(**data)
            existing_keys.add(key)
            importees += 1

        except Exception as e:
            erreurs += 1
            lignes_erreur.append({
                'ligne': line_num,
                'erreur': str(e),
                'immatriculation': row.get("Plaque d'immatriculation", '?'),
            })

    return {
        'importees':    importees,
        'doublons':     doublons,
        'erreurs':      erreurs,
        'lignes_erreur': lignes_erreur,
    }
