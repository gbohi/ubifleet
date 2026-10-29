#!/bin/bash
# ═══════════════════════════════════════════════════
#  UbiFleet — Script d'installation et démarrage
#  Ubipharm Fleet Management System
# ═══════════════════════════════════════════════════

set -e
echo "🚗 UbiFleet — Installation du backend Django"
echo "=============================================="

# 1. Environnement virtuel Python
echo "📦 Création de l'environnement virtuel..."
python3 -m venv venv
source venv/bin/activate

# 2. Dépendances
echo "📥 Installation des dépendances..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Base de données PostgreSQL
echo "🗄️  Configuration PostgreSQL..."
psql -U postgres <<SQL
CREATE USER ubifleet_user WITH PASSWORD 'ubifleet_pass_2025';
CREATE DATABASE ubifleet_db OWNER ubifleet_user;
GRANT ALL PRIVILEGES ON DATABASE ubifleet_db TO ubifleet_user;
SQL

# 4. Variables d'environnement
echo "⚙️  Configuration .env..."
cp .env.example .env

# 5. Migrations
echo "🔄 Application des migrations..."
python manage.py makemigrations accounts
python manage.py makemigrations vehicules
python manage.py makemigrations carburant
python manage.py makemigrations entretien
python manage.py makemigrations sinistres
python manage.py makemigrations budget
python manage.py makemigrations chauffeurs
python manage.py makemigrations alertes
python manage.py migrate

# 6. Données initiales
echo "🌱 Chargement des données de base..."
python manage.py loaddata initial_data.json

# 7. Superuser
echo "👤 Création du superutilisateur..."
python manage.py createsuperuser --email admin@ubipharm.ci --username admin

echo ""
echo "✅ Installation terminée !"
echo "=============================================="
echo "Démarrer le serveur :"
echo "  source venv/bin/activate"
echo "  python manage.py runserver"
echo ""
echo "Démarrer Celery (dans un autre terminal) :"
echo "  celery -A config worker -l info"
echo "  celery -A config beat -l info"
echo ""
echo "Documentation API :"
echo "  http://localhost:8000/api/docs/"
echo "  http://localhost:8000/api/redoc/"
echo "  http://localhost:8000/admin/"
