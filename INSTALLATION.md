# Installation de Mizzac

## Prérequis

- Python 3.12 ;
- SQLite pour une installation personnelle locale, ou PostgreSQL pour une
  instance durable ;
- Node.js 20.19, 22.12 ou 24+ uniquement pour reconstruire les ressources
  graphiques déjà versionnées.

La version applicative unique est Django 6.1.1. Les dépendances Python et
JavaScript sont verrouillées dans les fichiers `requirements-*.txt` et
`package-lock.json`.

## Première installation

Depuis la racine du dépôt :

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Générer une clé locale sans la copier dans le dépôt :

```bash
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Reporter le résultat dans `DJANGO_SECRET_KEY` du fichier `.env`, puis vérifier
les hôtes, l'origine CSRF, le fuseau horaire et la base. Pour SQLite :

```dotenv
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000
DJANGO_DB_ENGINE=django.db.backends.sqlite3
DJANGO_DB_NAME=db.sqlite3
```

Initialiser ensuite une base neuve :

```bash
cd Mizzac
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser
../.venv/bin/python manage.py check
../.venv/bin/python manage.py runserver
```

L'interface est alors disponible sur `http://localhost:8000/`. `runserver` est
réservé au développement ; un accès exposé sur un réseau doit utiliser HTTPS et
un serveur WSGI/ASGI correctement configuré.

## Ressources front-end

Les fichiers Tabler, icônes et ApexCharts nécessaires sont déjà locaux. Pour les
reconstruire depuis le lockfile :

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build:assets
```

Le navigateur n'a besoin d'aucun CDN.

## Vérification

```bash
make ci
cd Mizzac
../.venv/bin/python manage.py fundboard_healthcheck
```

Avant un déploiement HTTPS, renseigner tous les réglages sécurisés décrits dans
`.env.example`, puis lancer `manage.py check --deploy`.

## Base antérieure

Cette branche attend le schéma canonique construit depuis `FundBoard.0001`.
Ne jamais la pointer directement vers une ancienne base du prototype. La
procédure de sauvegarde et la stratégie de reprise sont décrites dans
`OPERATIONS_DATABASE.md`.

