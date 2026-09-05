# Exploitation des bases Mizzac

## Principe de sécurité

Ne jamais appliquer une migration sensible sans sauvegarde restaurée et testée.
Le dépôt ne contient pas de base utilisateur. À partir de la phase 3, la chaîne
historique `FundBoard.0001` à `0005` est remplacée par une migration initiale
canonique unique, car le propriétaire du projet a confirmé qu'aucune donnée
réelle n'était à reprendre.

Avant toute opération sur une base existante :

1. mettre l'application en maintenance et identifier le moteur ;
2. relever `python3 manage.py showmigrations FundBoard` ;
3. compter les lignes des tables métier sans exporter de données sensibles ;
4. créer une sauvegarde, calculer son SHA-256 et la stocker hors du dépôt ;
5. restaurer cette sauvegarde dans un environnement isolé ;
6. comparer migrations, nombres de lignes et totaux métier ;
7. exécuter la migration d'abord sur cette copie.

Une base ayant déjà enregistré une ancienne migration FundBoard est incompatible
avec cette branche : Django pourrait considérer le nouveau `0001_initial` comme
déjà appliqué alors que son schéma diffère. Ne lancez pas `migrate` dessus. Si
une telle base apparaît malgré la décision de repartir de zéro, archivez-la et
construisez un export/import explicite avant toute écriture. Pour le
développement actuel, supprimez uniquement la base locale jetable concernée,
recréez-la puis lancez la migration initiale.

## SQLite en développement

Configuration `.env` :

```dotenv
DJANGO_DB_ENGINE=django.db.backends.sqlite3
DJANGO_DB_NAME=db.sqlite3
```

Sauvegarde cohérente avec manifeste SHA-256, inventaire et permissions `0600` :

```bash
cd Mizzac
python3 manage.py backup_fundboard --destination /chemin/prive/backups-mizzac
python3 manage.py verify_fundboard_backup --backup /chemin/prive/backups-mizzac/mizzac-....sqlite3
```

Test de restauration vers un nouveau fichier uniquement :

```bash
python3 manage.py restore_fundboard_sqlite \
  --backup /chemin/prive/backups-mizzac/mizzac-....sqlite3 \
  --destination /tmp/mizzac-restore-test.sqlite3 \
  --confirm RESTORE_TO_NEW_DATABASE
```

Pointer une instance isolée vers cette copie, puis lancer `showmigrations`,
`check` et `fundboard_healthcheck`. Ne jamais versionner `*.sqlite3`.

## PostgreSQL en production

Installer les dépendances de production et renseigner les variables via le
gestionnaire de secrets de la plateforme :

```bash
python3 -m pip install -r requirements-production.txt
```

```dotenv
DJANGO_DB_ENGINE=django.db.backends.postgresql
DJANGO_DB_NAME=mizzac
DJANGO_DB_USER=mizzac
DJANGO_DB_PASSWORD=secret-externe-au-depot
DJANGO_DB_HOST=127.0.0.1
DJANGO_DB_PORT=5432
DJANGO_DB_CONN_MAX_AGE=60
```

La commande applicative appelle `pg_dump --format=custom`, produit le même
manifeste et vérifie l'archive avec `pg_restore --list` :

```bash
python3 manage.py backup_fundboard --destination /chemin/prive/backups-mizzac
python3 manage.py verify_fundboard_backup --backup /chemin/prive/backups-mizzac/mizzac-....dump
createdb mizzac_restore_test
pg_restore --dbname=mizzac_restore_test --exit-on-error /chemin/prive/backups-mizzac/mizzac-....dump
```

Adapter utilisateur, hôte et options à l'environnement. Une sauvegarde contenant
des données personnelles doit être chiffrée, à accès limité et soumise à une
politique de rétention.

## Réglages web de production

En plus de la base, définir au minimum une clé secrète forte,
`DJANGO_DEBUG=False`, les hôtes autorisés et les origines CSRF HTTPS. Après
validation du proxy TLS, activer la redirection SSL, les cookies sécurisés et
progressivement HSTS. Vérifier avant déploiement :

```bash
cd Mizzac
python3 manage.py check --deploy
python3 manage.py migrate --plan
```

`migrate --plan` est une lecture du plan ; l'exécution réelle reste conditionnée
à la sauvegarde et au test de restauration ci-dessus.
