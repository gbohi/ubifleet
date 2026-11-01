"""
UbiFleet — Moteur d'importation du fichier Total (CSV/Excel)
Gère : détection encodage, séparateur, mapping colonnes, doublons, erreurs
"""

import csv
import io
import re
import unicodedata
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


#: Colonnes sans lesquelles une ligne ne peut pas être exploitée
COLONNES_OBLIGATOIRES = ['date_transaction', 'numero_ticket', 'immatriculation', 'volume', 'montant',
                         'code_autorisation']


def _normaliser_entete(nom: str) -> str:
    """En-tête comparable : sans BOM, accents, casse, ponctuation ni espaces multiples."""
    nom = unicodedata.normalize('NFD', (nom or '').replace('\ufeff', ''))
    nom = ''.join(c for c in nom if unicodedata.category(c) != 'Mn').lower()
    return re.sub(r'[^a-z0-9]+', ' ', nom).strip()


ENTETES = {_normaliser_entete(col): champ for col, champ in COLUMN_MAP.items()}
LIBELLES = {champ: col for col, champ in COLUMN_MAP.items()}


class FichierInvalide(Exception):
    """Le fichier n'est pas un extrait de transactions Total exploitable."""


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
    value = (value or '').strip()
    # Cellule Excel convertie en texte : « 28/05/2026 00:00:00 » ou « 2026-05-28 00:00:00 »
    value = value.split(' ')[0]
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _parse_time(value: str):
    """Parse '00:39' en time."""
    value = (value or '').strip()
    value = value.split(' ')[-1] if ' ' in value else value   # « 1900-01-01 09:03:00 » (Excel)
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(value, fmt).time()
        except (ValueError, AttributeError):
            continue
    return None


def _detect_delimiter(content: str) -> str:
    """Détecte le séparateur ; ou ,"""
    first_line = content.split('\n')[0]
    return ';' if first_line.count(';') > first_line.count(',') else ','


def lire_lignes(fichier_bytes: bytes, encoding='utf-8-sig'):
    """(lignes {champ: texte}, colonnes ignorées) ; FichierInvalide si les
    colonnes indispensables manquent."""
    try:
        content = fichier_bytes.decode(encoding)
    except UnicodeDecodeError:
        content = fichier_bytes.decode('latin-1')
    reader = csv.reader(io.StringIO(content), delimiter=_detect_delimiter(content))
    entetes = next(reader, None)
    if not entetes:
        raise FichierInvalide("Le fichier est vide.")
    positions, ignorees = {}, []
    for i, nom in enumerate(entetes):
        champ = ENTETES.get(_normaliser_entete(nom))
        if champ and champ not in positions:
            positions[champ] = i
        elif nom.strip():
            ignorees.append(nom.strip())
    manquantes = [LIBELLES[c] for c in COLONNES_OBLIGATOIRES if c not in positions]
    if manquantes:
        raise FichierInvalide(
            "Ce fichier n'est pas un extrait de transactions TotalEnergies : colonne(s) manquante(s) : "
            + ', '.join(f"« {m} »" for m in manquantes) + '.')
    lignes = [{champ: (row[i] if i < len(row) else '') for champ, i in positions.items()}
              for row in reader if any(c.strip() for c in row)]
    if not lignes:
        raise FichierInvalide("Le fichier ne contient aucune transaction.")
    return lignes, ignorees


def importer_fichier(
    fichier_bytes: bytes,
    import_source,
    encoding='utf-8-sig'
) -> Dict:
    """
    Importe un fichier CSV/Excel Total (en-têtes reconnus même avec accents,
    casse ou espaces différents). Une ligne sans date, ticket ou plaque est
    rejetée avec son motif ; les doublons (ticket + code d'autorisation +
    date) sont ignorés. Tout ou rien en base : les lignes valides sont
    enregistrées ensemble.
    Retourne : { importees, doublons, erreurs, lignes_erreur, colonnes_ignorees }
    """
    from django.db import transaction
    from .models import TransactionCarburant

    lignes, ignorees = lire_lignes(fichier_bytes, encoding)
    importees = doublons = erreurs = 0
    lignes_erreur, a_creer = [], []
    existing_keys = set(TransactionCarburant.objects.values_list(
        'numero_ticket', 'code_autorisation', 'date_transaction'))

    for line_num, row in enumerate(lignes, start=2):
        data = {'import_source': import_source}
        for champ, raw in row.items():
            raw = (raw or '').strip()
            if champ == 'date_transaction':
                data[champ] = _parse_date(raw)
            elif champ == 'heure_transaction':
                data[champ] = _parse_time(raw)
            elif champ in DECIMAL_FIELDS:
                data[champ] = _parse_decimal(raw)
            else:
                data[champ] = raw[:TransactionCarburant._meta.get_field(champ).max_length or None]
        motif = ('Date de transaction illisible ou absente' if not data.get('date_transaction') else
                 'Numéro de ticket absent' if not data.get('numero_ticket') else
                 "Plaque d'immatriculation absente" if not data.get('immatriculation') else
                 'Volume ou montant illisible' if data.get('volume') is None or data.get('montant') is None else '')
        if motif:
            erreurs += 1
            lignes_erreur.append({'ligne': line_num, 'erreur': motif, 'immatriculation': row.get('immatriculation', '')})
            continue
        key = (data['numero_ticket'], data.get('code_autorisation', ''), data['date_transaction'])
        if key in existing_keys:
            doublons += 1
            continue
        existing_keys.add(key)
        a_creer.append(TransactionCarburant(**data))

    from .annulations import marquer_annulations
    with transaction.atomic():
        TransactionCarburant.objects.bulk_create(a_creer, batch_size=500)
        marquer_annulations({t.immatriculation for t in a_creer})
    importees = len(a_creer)
    return {
        'importees':    importees,
        'doublons':     doublons,
        'erreurs':      erreurs,
        'lignes_erreur': lignes_erreur,
        'colonnes_ignorees': ignorees,
    }
