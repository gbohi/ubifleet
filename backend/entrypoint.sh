#!/bin/bash
set -e

echo "======================================="
echo "   UbiFleet Backend - Démarrage"
echo "======================================="

# Attendre PostgreSQL
echo "[1/5] Attente de PostgreSQL..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        host=os.environ.get('DB_HOST','db'),
        port=os.environ.get('DB_PORT','5432'),
    )
    sys.exit(0)
except Exception as e:
    print(f'  PostgreSQL pas encore prêt: {e}')
    sys.exit(1)
"; do
  sleep 2
done
echo "  PostgreSQL OK"

# Migrations
echo "[2/5] Migrations..."
python manage.py migrate --noinput
echo "  Migrations OK"

# Static files
echo "[3/5] Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear 2>/dev/null || true
echo "  Static OK"

# Rôles système (créés s'ils manquent ; noms et permissions inchangés)
echo "[4/5] Rôles système..."
python manage.py init_roles --roles-seulement

# Premier administrateur : uniquement si aucun super administrateur actif
# n'existe et si ADMIN_EMAIL / ADMIN_PASSWORD sont fournis (.env). Aucun mot
# de passe n'est écrit dans ce script.
echo "[5/5] Vérification de l'administrateur..."
python manage.py shell << 'PYEOF'
import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.accounts.models import Role

User = get_user_model()
if User.objects.filter(is_active=True, role__niveau__gte=10).exists():
    print("  Super administrateur existant OK")
else:
    email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    mdp = os.environ.get('ADMIN_PASSWORD', '')
    if not email or not mdp:
        print("  ATTENTION : aucun super administrateur. Renseignez ADMIN_EMAIL et "
              "ADMIN_PASSWORD dans .env puis redémarrez le conteneur.")
    else:
        try:
            validate_password(mdp)
        except ValidationError as e:
            print("  ATTENTION : ADMIN_PASSWORD refusé : " + ' '.join(e.messages))
        else:
            role = Role.objects.get(code='super_admin')
            u = User.objects.filter(email__iexact=email).first()
            if u is None:
                u = User.objects.create_user(email=email, username=email.split('@')[0], password=mdp,
                                             first_name='Administrateur', last_name='UbiFleet')
            u.role, u.is_active, u.is_staff, u.is_superuser = role, True, True, True
            u.set_password(mdp)
            u.save()
            print(f"  Super administrateur {email} prêt. Retirez ADMIN_PASSWORD de .env "
                  "et changez le mot de passe depuis l'application.")
PYEOF

echo "======================================="
echo "   Démarrage du serveur Gunicorn"
echo "======================================="
exec "$@"
