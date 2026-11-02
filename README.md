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
├── backend/       API Django
├── web/           Interface Angular
└── deploiement/   Docker Compose, nginx, procédure de déploiement
```

## Modules

Véhicules · Carburant · Entretien & réparations · Assurance & sinistres ·
Chauffeurs · Relevés kilométriques · Demandes (workflow de validation) ·
Contrôle véhicule · Alertes · Budget · Rapports · Paramétrage

## Installation en développement

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # puis renseigner les valeurs
python manage.py migrate
python manage.py init_roles      # rôles système et permissions par défaut
python manage.py createsuperuser  # reçoit le rôle Super Admin
DEBUG=True python manage.py runserver
```

### Frontend

```bash
cd web
npm install
ng serve
```

L'application est disponible sur http://localhost:4200

## Mise en production

### Configuration (`backend/.env`, à partir de `.env.example`)

| Variable | Rôle |
|---|---|
| `SECRET_KEY` | **Obligatoire** : le serveur refuse de démarrer sans elle. À générer une fois : `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | `False` en production (valeur par défaut) |
| `ALLOWED_HOSTS` | Adresses par lesquelles on joint le serveur (ex. `192.168.2.10`) |
| `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | Adresse du site avec son schéma (ex. `http://192.168.2.10`) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Premier super administrateur, créé au démarrage s'il n'en existe aucun. Retirer `ADMIN_PASSWORD` ensuite |
| `DB_PASSWORD` | Mot de passe fort propre à l'installation |
| `HTTPS`, `HSTS_SECONDS` | Voir ci-dessous |

Au démarrage, le conteneur applique les migrations, vérifie les rôles système
(`init_roles --roles-seulement` : création s'ils manquent, sans toucher aux noms
ni aux permissions réglées) et crée le premier administrateur si besoin.
Aucun mot de passe n'est écrit dans le code.

### HTTPS

L'interface appelle l'API à la même adresse que le site (`/api/v1`) : le serveur
web en frontal sert l'interface et transmet `/api/` et `/media/` à Django.

- Accès uniquement depuis le réseau local de confiance : HTTP est acceptable.
- Accès depuis les agences distantes par Internet (sans VPN) ou par Wi-Fi :
  installer un certificat sur le serveur web (certificat interne ou
  auto-signé suffisant), lui faire transmettre l'en-tête
  `X-Forwarded-Proto`, puis dans `.env` : `HTTPS=True` et les origines en
  `https://`. Activer `HSTS_SECONDS=31536000` seulement une fois HTTPS stable.

### Sécurité en place

Mode debug désactivé par défaut, documentation de l'API publiée seulement en
développement, connexion limitée à 10 tentatives par minute et par adresse IP
(`THROTTLE_CONNEXION`), en-têtes de sécurité (anti-iframe, type MIME, referrer),
mots de passe soumis aux règles de complexité, journal des erreurs sur la
sortie standard.

### Commandes

Procédure complète (sauvegarde, migrations, restauration) : `deploiement/DEPLOIEMENT.md`.

```bash
cd deploiement
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
