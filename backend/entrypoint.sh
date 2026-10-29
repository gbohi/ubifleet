#!/bin/bash
set -e

echo "======================================="
echo "   UbiFleet Backend - Démarrage"
echo "======================================="

# Attendre PostgreSQL
echo "[1/4] Attente de PostgreSQL..."
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
echo "[2/4] Migrations..."
python manage.py migrate --noinput
echo "  Migrations OK"

# Static files
echo "[3/4] Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear 2>/dev/null || true
echo "  Static OK"

# Superuser
echo "[4/4] Vérification du superuser..."
python manage.py shell << 'PYEOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    u = User.objects.create_superuser('admin', 'admin@ubifleet.ci', 'Admin@2024!')
    print("  Superuser 'admin' créé — mot de passe: Admin@2024!")
    print("  IMPORTANT: changez ce mot de passe immédiatement!")
else:
    print("  Superuser existant OK")
PYEOF

echo "======================================="
echo "   Démarrage du serveur Gunicorn"
echo "======================================="
exec "$@"
