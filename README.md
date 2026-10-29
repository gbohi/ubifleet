# UbiFleet

Système de gestion de flotte automobile — Ubipharm.

## Architecture

| Composant | Technologie |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Frontend | Angular 18 (standalone components, signals) |
| Base de données | PostgreSQL 16 |
| Tâches asynchrones | Celery + Redis |
| Déploiement | Docker Compose + Nginx |

## Structure du dépôt

```
ubifleet/
├── ubifleet_backend/     API Django
├── ubifleet-angular/     Interface Angular
└── docker-ubifleet/      Fichiers de déploiement
```

## Modules

Véhicules · Carburant · Entretien & réparations · Assurance & sinistres ·
Chauffeurs · Relevés kilométriques · Demandes (workflow de validation) ·
Contrôle véhicule · Alertes · Budget · Rapports · Paramétrage

## Installation en développement

### Backend

```bash
cd ubifleet_backend
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # puis renseigner les valeurs
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Frontend

```bash
cd ubifleet-angular
npm install
ng serve
```

L'application est disponible sur http://localhost:4200

## Déploiement

Voir `docker-ubifleet/DEPLOIEMENT.md`.

```bash
cd docker-ubifleet
docker compose build --no-cache backend frontend
docker compose run --rm --entrypoint "" backend python manage.py migrate --plan
docker compose run --rm --entrypoint "" backend python manage.py migrate
docker compose up -d
```

## Conventions

- Les migrations sont versionnées et livrées avec le code.
- Toujours vérifier `migrate --plan` avant d'appliquer en production.
- L'historique des migrations a été consolidé (`0001_squashed` par app, qui
  remplace les anciennes migrations via `replaces`). Sur une base existante,
  `migrate --plan` ne doit afficher aucune opération : Django enregistre
  simplement les migrations consolidées, sans exécuter de SQL.
- Le fichier `.env` n'est jamais commité ; se référer à `.env.example`.
