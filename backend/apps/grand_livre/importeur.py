"""
UbiFleet — Moteur d'importation du Grand Livre (XLS/XLSX/CSV)
Règles :
  - Ligne 1 : en-tête (ignorée)
  - Ligne 2 : code_agence (col 0) + libelle_agence (col 1)
  - Lignes suivantes : écritures (ignorer les lignes "Solde du compte")
  - Ne pas importer la colonne Solde
"""
import io
import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple


# Mapping : index colonne → champ modèle
# col0=Compte col1=Libellé_compte col2=Analytique col3=Comptable
# col4=Origine col5=Pièce col6=N°ligne col7=N°Analytique col8=Libellé_écriture
# col9=Débit col10=Crédit   (col11=Solde → ignoré)
COL_MAP = {
    0:  'compte',
    1:  'libelle_compte',
    2:  'date_analytique',
    3:  'date_comptable',
    4:  'origine',
    5:  'piece',
    6:  'no_ligne',
    7:  'no_analytique',
    8:  'libelle_ecriture',
    9:  'debit',
    10: 'credit',
    # 11 = Solde → ignoré
}

DATE_FIELDS    = {'date_analytique', 'date_comptable'}
DECIMAL_FIELDS = {'debit', 'credit'}
INT_FIELDS     = {'no_ligne', 'no_analytique'}
EXCEL_EPOCH    = datetime.date(1899, 12, 30)


def _texte(val) -> str:
    """Valeur de cellule → texte : 401100.0 (nombre Excel) devient « 401100 »."""
    if val is None:
        return ''
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    if isinstance(val, datetime.datetime):
        return val.date().isoformat()
    if isinstance(val, datetime.date):
        return val.isoformat()
    return str(val).strip()


def _parse_date(val) -> datetime.date | None:
    """Date Python, numéro de série Excel ou texte (jj/mm/aaaa, aaaa-mm-jj…)."""
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    s = str(val or '').strip()
    if not s or s == 'None':
        return None
    try:
        n = float(s.replace(',', '.'))
        if 1 <= n < 100000:  # numéro de série Excel (1900 → 2173)
            return EXCEL_EPOCH + datetime.timedelta(days=int(n))
        return None
    except ValueError:
        pass
    s = s.split(' ')[0].split('T')[0]  # « 2026-01-05 00:00:00 »
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%d.%m.%Y'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date illisible : « {val} »")


def _parse_decimal(val) -> Decimal:
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val)).quantize(Decimal('0.01'))
    s = str(val or '').strip().replace('\u00a0', '').replace('\u202f', '').replace(' ', '')
    if not s or s == 'None':
        return Decimal('0')
    if ',' in s and '.' in s:          # 1.234,56 ou 1,234.56
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    else:
        s = s.replace(',', '.')
    try:
        return Decimal(s).quantize(Decimal('0.01'))
    except InvalidOperation:
        raise ValueError(f"Montant illisible : « {val} »")


def _parse_int(val) -> int | None:
    s = _texte(val)
    if not s:
        return None
    try:
        return int(float(s.replace(',', '.')))
    except ValueError:
        return None


def _read_xls(file_bytes: bytes) -> Tuple[str, str, List[list]]:
    """Lit un fichier XLS et retourne (code_agence, libelle_agence, lignes_data)."""
    import xlrd
    wb = xlrd.open_workbook(file_contents=file_bytes)
    ws = wb.sheet_by_index(0)
    if ws.nrows < 2:
        raise ValueError("Le fichier ne contient pas assez de lignes.")

    def valeur(i, j):
        cell = ws.cell(i, j)
        if cell.ctype == xlrd.XL_CELL_DATE:
            try:
                return xlrd.xldate.xldate_as_datetime(cell.value, wb.datemode).date()
            except Exception:
                return cell.value
        return cell.value

    code_agence    = _texte(valeur(1, 0))
    libelle_agence = _texte(valeur(1, 1)) if ws.ncols > 1 else ''
    rows = [[valeur(i, j) for j in range(ws.ncols)] for i in range(2, ws.nrows)]
    return code_agence, libelle_agence, rows


def _read_xlsx(file_bytes: bytes) -> Tuple[str, str, List[list]]:
    """Lit un fichier XLSX."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    if len(all_rows) < 2:
        raise ValueError("Le fichier ne contient pas assez de lignes.")
    ligne2 = all_rows[1] + [None, None]
    return _texte(ligne2[0]), _texte(ligne2[1]), all_rows[2:]


def _read_csv(file_bytes: bytes) -> Tuple[str, str, List[list]]:
    """Lit un fichier CSV (séparateur ; ou ,)."""
    import csv
    try:
        content = file_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        content = file_bytes.decode('latin-1')

    first_line = content.split('\n')[0]
    delimiter  = ';' if first_line.count(';') >= first_line.count(',') else ','
    reader     = list(csv.reader(io.StringIO(content), delimiter=delimiter))
    if len(reader) < 2:
        raise ValueError("Le fichier CSV ne contient pas assez de lignes.")
    ligne2 = reader[1] + ['', '']
    return ligne2[0].strip(), ligne2[1].strip(), reader[2:]


def importer_grand_livre(fichier_bytes: bytes, nom_fichier: str, import_source) -> Dict:
    """
    Importe un fichier de grand livre (XLS/XLSX/CSV), en une seule transaction.
    Retourne : { importees, doublons, erreurs, lignes_erreur, code_agence, libelle_agence }
    """
    from django.db import transaction
    from .models import LigneGrandLivre

    ext = nom_fichier.lower()
    try:
        if ext.endswith('.xlsx'):
            code_agence, libelle_agence, rows = _read_xlsx(fichier_bytes)
        elif ext.endswith('.xls'):
            code_agence, libelle_agence, rows = _read_xls(fichier_bytes)
        else:
            code_agence, libelle_agence, rows = _read_csv(fichier_bytes)
    except ValueError:
        raise
    except Exception:
        raise ValueError("Fichier illisible : vérifiez qu'il s'agit bien d'un export XLS, XLSX ou CSV du grand livre.")

    code_agence = code_agence.strip().upper()
    if not code_agence or any(c.isspace() for c in code_agence) or len(code_agence) > 20:
        raise ValueError("Impossible de lire le code agence (ligne 2, colonne A).")

    # Clés existantes pour déduplication
    existing_keys = set(
        LigneGrandLivre.objects.filter(code_agence=code_agence).values_list(
            'compte', 'piece', 'no_ligne', 'date_analytique'
        )
    )

    a_creer       = []
    doublons      = 0
    lignes_erreur = []

    for line_num, row in enumerate(rows, start=3):
        row = list(row or [])
        first_cell = _texte(row[0]) if row else ''
        # Lignes vides, « Solde du compte », totaux : ignorées
        if not first_cell or first_cell.lower().startswith(('solde', 'total')):
            continue
        if not any(c.isdigit() for c in first_cell):
            continue

        try:
            data: Dict = {
                'import_source':  import_source,
                'code_agence':    code_agence,
                'libelle_agence': libelle_agence,
            }
            for col_idx, field_name in COL_MAP.items():
                raw = row[col_idx] if col_idx < len(row) else ''
                if field_name in DATE_FIELDS:
                    data[field_name] = _parse_date(raw)
                elif field_name in DECIMAL_FIELDS:
                    data[field_name] = _parse_decimal(raw)
                elif field_name in INT_FIELDS:
                    data[field_name] = _parse_int(raw)
                else:
                    data[field_name] = _texte(raw)
            for champ, maxi in (('compte', 20), ('libelle_compte', 200), ('origine', 20),
                                ('piece', 50), ('libelle_ecriture', 255)):
                if len(data[champ]) > maxi:
                    if champ in ('compte', 'piece', 'origine'):
                        raise ValueError(f"{champ} trop long ({len(data[champ])} caractères)")
                    data[champ] = data[champ][:maxi]

            key = (data['compte'], data['piece'], data['no_ligne'], data['date_analytique'])
            if key in existing_keys:
                doublons += 1
                continue
            existing_keys.add(key)
            a_creer.append(LigneGrandLivre(**data))

        except Exception as exc:
            lignes_erreur.append({
                'ligne':  line_num,
                'erreur': str(exc),
                'compte': first_cell or '?',
            })

    with transaction.atomic():
        LigneGrandLivre.objects.bulk_create(a_creer, batch_size=1000)

    return {
        'importees':     len(a_creer),
        'doublons':      doublons,
        'erreurs':       len(lignes_erreur),
        'lignes_erreur': lignes_erreur,
        'code_agence':   code_agence,
        'libelle_agence':libelle_agence,
    }
