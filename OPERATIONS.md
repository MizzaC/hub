# Exploitation personnelle de FundBoard

## Maintenance planifiée

La commande unifiée exécute, pour chaque utilisateur actif :

1. avec `--with-network` uniquement, le taux EUR/USD, les cours des instruments
   réellement suivis et les connecteurs en lecture seule arrivés à échéance ;
2. le snapshot patrimonial quotidien depuis le dernier état valide stocké ;
3. le traitement des ordres virtuels ouverts et un snapshot virtuel quotidien.

Sans option réseau, aucun appel HTTP n'est possible :

```bash
cd Mizzac
../.venv/bin/python manage.py run_fundboard_maintenance
```

Planification complète :

```bash
../.venv/bin/python manage.py run_fundboard_maintenance \
  --with-network --fail-on-partial
```

`--username` limite l'exécution. `--force-network` ignore exceptionnellement
`next_sync_at` et exige `--with-network`. Une contrainte interdit deux
maintenances simultanées pour un même utilisateur. Une exécution `RUNNING`
abandonnée depuis deux heures est clôturée avant reprise. Les intervalles sont
configurés par `FUNDBOARD_SYNC_INTERVAL_MINUTES`,
`FUNDBOARD_SYNC_RETRY_MINUTES` et `FUNDBOARD_MAINTENANCE_STALE_MINUTES`.

La page **FundBoard → Exploitation** affiche résultats, compteurs et identifiants
de corrélation. Son bouton reste strictement local. Les synchronisations réseau
restent explicites depuis une connexion ou la commande ci-dessus.

### cron

Exemple horaire, à adapter aux chemins locaux :

```cron
17 * * * * cd /chemin/mizzac/Mizzac && ../.venv/bin/python manage.py run_fundboard_maintenance --with-network --fail-on-partial >> /chemin/prive/logs/maintenance.log 2>&1
```

Les exemples `systemd` durcis se trouvent dans `deploy/systemd/`. Copier puis
adapter les chemins, l'utilisateur, le fichier d'environnement et
`ReadWritePaths` avant de les activer. Le fichier d'environnement doit être en
mode `0600` et hors du dépôt. Les modèles supposent une base SQLite sous
`/var/lib/mizzac` afin de laisser le code applicatif en lecture seule.

## Santé et journaux

```bash
../.venv/bin/python manage.py fundboard_healthcheck
../.venv/bin/python manage.py fundboard_healthcheck --json
../.venv/bin/python manage.py fundboard_healthcheck --strict
```

Le contrôle vérifie la base, les migrations, les maintenances ou
synchronisations bloquées, les connexions en erreur et les échéances dépassées.
Le mode strict retourne un code non nul pour un avertissement, pratique pour un
moniteur local.

`DJANGO_LOG_JSON=True` produit des lignes JSON adaptées à `journald` ou aux logs
d'un conteneur. Les champs de contexte sont limités et les motifs courants de
secret sont remplacés par `[REDACTED]`. Ne jamais envoyer les fichiers de logs à
un service externe sans revue.

## Sauvegarde vérifiée

Créer d'abord un répertoire privé hors du dépôt :

```bash
install -d -m 700 /chemin/prive/backups-mizzac
../.venv/bin/python manage.py backup_fundboard \
  --destination /chemin/prive/backups-mizzac
```

SQLite utilise l'API de sauvegarde cohérente de SQLite. PostgreSQL utilise
`pg_dump --format=custom` et exige les outils clients PostgreSQL. Chaque archive
est en mode `0600` et accompagnée d'un manifeste contenant SHA-256, taille et
inventaire technique, sans ligne métier.

Vérification :

```bash
../.venv/bin/python manage.py verify_fundboard_backup \
  --backup /chemin/prive/backups-mizzac/mizzac-....sqlite3
```

Pour SQLite, le contrôle relit l'empreinte, `integrity_check`, les clés
étrangères, les migrations et les nombres de lignes. Une restauration automatisée
ne peut viser qu'un nouveau fichier et exige une confirmation littérale :

```bash
../.venv/bin/python manage.py restore_fundboard_sqlite \
  --backup /chemin/prive/backups-mizzac/mizzac-....sqlite3 \
  --destination /tmp/mizzac-restore-test.sqlite3 \
  --confirm RESTORE_TO_NEW_DATABASE
```

Pointer ensuite une instance isolée vers ce fichier, lancer `showmigrations`,
`check` et `fundboard_healthcheck`. La commande refuse une destination existante
et la base active. Pour PostgreSQL, restaurer manuellement vers une nouvelle base
avec `pg_restore --exit-on-error`, puis effectuer les mêmes contrôles.

Une sauvegarde non restaurée et vérifiée n'est pas considérée comme valide.
Conserver plusieurs générations chiffrées, au moins une copie hors machine, et
tester périodiquement la restauration avant de supprimer les anciennes copies.

## Réponse à incident

1. désactiver le timer réseau et conserver les journaux ;
2. lancer le healthcheck et relever les identifiants de corrélation ;
3. ne pas relancer en boucle un connecteur en erreur ;
4. vérifier la dernière sauvegarde et la restaurer dans un fichier/base isolé ;
5. révoquer les accès chez Binance ou l'agrégateur si un secret est suspecté ;
6. changer le secret externe et la `DJANGO_SECRET_KEY` si nécessaire, puis
   invalider les sessions.
