# UbiFleet — Déploiement

Ce dossier contient tout le déploiement Docker. Les images sont construites
directement depuis le code du dépôt (`../backend`, `../web`) : plus besoin de
copier le code à la main dans des sous-dossiers.

```
ubifleet/                (dépôt)
├── backend/             API Django
├── web/                 Interface Angular
└── deploiement/
    ├── docker-compose.yml
    ├── nginx/nginx.conf
    └── .env             (à créer, jamais commité)
```

## 1. Fichier `.env`

Partir du modèle `../backend/.env.example` :

```bash
cp ../backend/.env.example .env
```

À renseigner au minimum :

- `SECRET_KEY` : **nouvelle clé**, la clé de démonstration est refusée au démarrage.
  `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`
  (changer la clé déconnecte tous les utilisateurs : ils se reconnectent simplement).
- `ALLOWED_HOSTS` : adresse(s) du serveur, ex. `10.30.2.118,localhost`.
- `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` : ex. `http://10.30.2.118`.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` : **identiques à l'installation existante**
  (sinon PostgreSQL refuse la connexion à la base déjà créée).
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` : seulement pour une installation neuve, ou
  s'il n'existe aucun super administrateur actif.

## 2. Mise à jour d'une installation existante (données conservées)

Les données (véhicules, utilisateurs, agences, prises…) restent dans la base :
les migrations la font évoluer sans la recréer.

```bash
# 1. Sauvegarde AVANT toute chose (à conserver hors du serveur)
docker compose exec -T db pg_dump -U ubifleet_user -d ubifleet_db -Fc > sauvegarde_$(date +%Y%m%d_%H%M).dump

# 2. Récupérer le code
cd ~/ubifleet && git pull && cd deploiement

# 3. Construire les nouvelles images
docker compose build backend celery celery-beat frontend

# 4. Voir ce que les migrations vont faire, sans rien appliquer
docker compose run --rm --entrypoint "" backend python manage.py migrate --plan

# 5. Appliquer (le démarrage du backend applique aussi les migrations)
docker compose up -d

# 6. Suivre le démarrage
docker compose logs -f backend
```

En cas de problème, restaurer la sauvegarde :

```bash
docker compose stop backend celery celery-beat
docker compose exec -T db pg_restore -U ubifleet_user -d ubifleet_db --clean --if-exists < sauvegarde_AAAAMMJJ_HHMM.dump
```

## 3. Installation neuve

```bash
cp ../backend/.env.example .env      # puis renseigner (dont ADMIN_EMAIL / ADMIN_PASSWORD)
docker compose up -d --build
docker compose logs -f backend
```

Le premier démarrage crée les rôles système et le super administrateur
indiqué dans `.env`. Retirer ensuite `ADMIN_PASSWORD` du fichier.

## 4. Vérifier

```bash
docker compose ps
```

Tous les services doivent être `running` : `ubifleet_db` (healthy),
`ubifleet_redis`, `ubifleet_backend`, `ubifleet_celery`,
`ubifleet_celery_beat`, `ubifleet_frontend`, `ubifleet_nginx`.

- Application : `http://<adresse du serveur>`
- Administration Django : `http://<adresse du serveur>/django-admin/`
  (comptes super administrateur uniquement)

## 5. HTTPS (facultatif en réseau local)

Nécessaire si des agences se connectent par Internet sans VPN, recommandé en
Wi-Fi. Installer le certificat dans nginx (`listen 443 ssl`, `ssl_certificate`,
`ssl_certificate_key`, monter les fichiers en volume, exposer le port 443),
garder `X-Forwarded-Proto $scheme`, puis dans `.env` : `HTTPS=True` et les
origines en `https://`. `HSTS_SECONDS=31536000` seulement une fois HTTPS stable.

## Commandes utiles

```bash
docker compose logs -f backend            # journal de l'API
docker compose restart backend
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py changepassword <email>
docker system df                          # espace disque Docker
```

## Changements par rapport à l'ancien dossier `docker-ubifleet`

- Construction depuis le dépôt (plus de copie du code).
- Service `celery-beat` ajouté : la vérification quotidienne des alertes
  (7 h) ne se déclenchait jamais.
- Les services Celery ne relancent plus les migrations au démarrage
  (seul le backend les applique, sans exécution en parallèle).
- nginx répond quelle que soit l'adresse du serveur (`server_name _`).
- Plus de mot de passe administrateur par défaut (`Admin@2024!`).
