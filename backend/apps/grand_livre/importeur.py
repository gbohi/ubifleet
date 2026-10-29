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


def _excel_date(val) -> datetime.date | None:
    """Convertit un numéro de série Excel en date Python."""
    try:
        n = int(float(str(val).strip()))
        return EXCEL_EPOCH + datetime.timedelta(days=n)
    except (ValueError, TypeError):
        return None


def _parse_date(val: str) -> datetime.date | None:
    """Parse une date string ou numérique."""
    s = str(val).strip()
    if not s or s in ('', 'None'):
        return None
    # Numérique → date Excel
    try:
        return _excel_date(float(s))
    except ValueError:
        pass
    # String textuelle
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val) -> Decimal:
    s = str(val).strip().replace(' ', '').replace(',', '.')
    if not s or s in ('', 'None'):
        return Decimal('0')
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal('0')


def _parse_int(val) -> int | None:
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def _read_xls(file_bytes: bytes) -> Tuple[str, str, List[List[str]]]:
    """Lit un fichier XLS et retourne (code_agence, libelle_agence, lignes_data)."""
    import xlrd
    wb = xlrd.open_workbook(file_contents=file_bytes)
    ws = wb.sheet_by_index(0)

    if ws.nrows < 2:
        raise ValueError("Le fichier ne contient pas assez de lignes.")

    # Ligne 2 = agence
    code_agence    = str(ws.cell_value(1, 0)).strip()
    libelle_agence = str(ws.cell_value(1, 1)).strip()

    # Lignes 3+ = données
    rows = []
    for i in range(2, ws.nrows):
        row = [str(ws.cell_value(i, j)).strip() for j in range(ws.ncols)]
        rows.append(row)

    return code_agence, libelle_agence, rows


def _read_xlsx(file_bytes: bytes) -> Tuple[str, str, List[List[str]]]:
    """Lit un fichier XLSX."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active

    all_rows = list(ws.iter_rows(values_only=True))
    if len(all_rows) < 2:
        raise ValueError("Le fichier ne contient pas assez de lignes.")

    code_agence    = str(all_rows[1][0] or '').strip()
    libelle_agence = str(all_rows[1][1] or '').strip()

    rows = []
    for row in all_rows[2:]:
        rows.append([str(v or '').strip() for v in row])

    return code_agence, libelle_agence, rows


def _read_csv(file_bytes: bytes) -> Tuple[str, str, List[List[str]]]:
    """Lit un fichier CSV (séparateur ; ou ,)."""
    import csv
    for enc in ('utf-8-sig', 'latin-1'):
        try:
            content = file_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            content = file_bytes.decode('latin-1')

    first_line = content.split('\n')[0]
    delimiter  = ';' if first_line.count(';') >= first_line.count(',') else ','

    reader     = list(csv.reader(io.StringIO(content), delimiter=delimiter))
    if len(reader) < 2:
        raise ValueError("Le fichier CSV ne contient pas assez de lignes.")

    code_agence    = reader[1][0].strip() if len(reader[1]) > 0 else ''
    libelle_agence = reader[1][1].strip() if len(reader[1]) > 1 else ''
    rows           = reader[2:]

    return code_agence, libelle_agence, rows


def importer_grand_livre(fichier_bytes: bytes, nom_fichier: str, import_source) -> Dict:
    """
    Importe un fichier de grand livre (XLS/XLSX/CSV).
    Retourne : { importees, doublons, erreurs, lignes_erreur }
    """
    from .models import LigneGrandLivre

    ext = nom_fichier.lower()

    if ext.endswith('.xls'):
        code_agence, libelle_agence, rows = _read_xls(fichier_bytes)
    elif ext.endswith('.xlsx'):
        code_agence, libelle_agence, rows = _read_xlsx(fichier_bytes)
    else:
        code_agence, libelle_agence, rows = _read_csv(fichier_bytes)

    if not code_agence:
        raise ValueError("Impossible de lire le code agence (ligne 2, colonne 1).")

    # Clés existantes pour déduplication
    existing_keys = set(
        LigneGrandLivre.objects.filter(code_agence=code_agence).values_list(
            'compte', 'piece', 'no_ligne', 'date_analytique'
        )
    )

    importees     = 0
    doublons      = 0
    erreurs       = 0
    lignes_erreur = []

    for line_num, row in enumerate(rows, start=3):
        # Ignorer les lignes "Solde du compte" et les lignes vides
        first_cell = row[0] if row else ''
        if not first_cell or first_cell.lower().startswith('solde'):
            continue
        # Ignorer lignes où le compte n'est pas numérique
        if not any(c.isdigit() for c in first_cell):
            continue

        try:
            data: Dict = {
                'import_source': import_source,
                'code_agence':   code_agence,
                'libelle_agence':libelle_agence,
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
                    data[field_name] = raw.strip()

            # Clé d'unicité
            key = (
                str(data.get('compte', '')),
                str(data.get('piece', '')),
                data.get('no_ligne'),
                data.get('date_analytique'),
            )

            if key in existing_keys:
                doublons += 1
                continue

            LigneGrandLivre.objects.create(**data)
            existing_keys.add(key)
            importees += 1

        except Exception as exc:
            erreurs += 1
            lignes_erreur.append({
                'ligne':   line_num,
                'erreur':  str(exc),
                'compte':  row[0] if row else '?',
            })

    return {
        'importees':     importees,
        'doublons':      doublons,
        'erreurs':       erreurs,
        'lignes_erreur': lignes_erreur,
        'code_agence':   code_agence,
        'libelle_agence':libelle_agence,
    }
