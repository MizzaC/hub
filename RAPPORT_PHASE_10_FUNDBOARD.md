# Rapport de phase 10 — Automatisation, durcissement et documentation

Date de validation : 5 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`  
Version unique : Python 3.12 / Django 6.1.1

## 1. Résumé du résultat fonctionnel

La phase 10 est terminée. FundBoard dispose d'une maintenance unifiée,
planifiable sans ajouter Celery ou un autre service : snapshots patrimoniaux,
ordres virtuels ouverts et snapshots virtuels sont traités localement. Les
appels Frankfurter, Yahoo/CoinGecko et les connecteurs financiers restent
strictement désactivés par défaut et exigent `--with-network`.

Chaque passage crée un `MaintenanceRun` privé avec statut, compteurs, origine,
horodatage et UUID de corrélation. Une contrainte empêche deux passages actifs
pour le même utilisateur et permet de clôturer une exécution abandonnée. Les
connexions utilisent `next_sync_at`, avec délai normal et délai de reprise
configurables.

La page **Exploitation** présente santé, migrations, connexions à contrôler,
échéances, ordres virtuels ouverts et historiques de maintenance/connecteurs.
Son bouton ne lance que les tâches locales.

Des commandes créent, vérifient et restaurent les sauvegardes. SQLite est copié
par son API cohérente, accompagné d'un manifeste SHA-256, vérifié par intégrité,
clés étrangères, migrations et nombres de lignes, puis restaurable uniquement
vers un nouveau fichier. PostgreSQL utilise `pg_dump`/`pg_restore` sans mot de
passe dans la ligne de commande.

## 2. Constats et décisions prises

- Pour cet usage personnel, cron ou un timer systemd est plus simple et plus
  robuste qu'une pile Celery/Redis. Quatre unités systemd adaptables sont
  fournies avec restrictions de système de fichiers et privilèges.
- Aucun job réseau ne s'exécute sans `--with-network`. Les tests et le bouton UI
  vérifient explicitement l'absence de requête HTTP.
- L'actualisation réseau cible les instruments privés, détenus, utilisés comme
  benchmark ou présents dans une watchlist virtuelle. L'historique complet
  n'est pas retéléchargé à chaque passage.
- Une synchronisation réussie programme la prochaine échéance à six heures par
  défaut ; un échec programme une nouvelle tentative après trente minutes.
- Les erreurs persistées et compteurs restent publics et expurgés. Les logs
  texte ou JSON filtrent tokens, secrets, mots de passe, cookies, PIN et 2FA,
  y compris dans les traces d'exception.
- Les en-têtes navigateur et cookies ont été durcis. SSL, cookies Secure et
  HSTS restent conditionnés à la présence effective d'un proxy HTTPS.
- Les sauvegardes et manifestes sont explicitement exclus de Git et créés en
  mode `0600`. Une restauration ne remplace jamais automatiquement la base
  active.
- L'index `(user, next_sync_at)` optimise la sélection des connexions dues. La
  page d'exploitation charge les relations de connexion en une requête stable ;
  un test confirme que son nombre de requêtes ne croît pas avec les lignes.
- La CI GitHub est en lecture seule, limitée à vingt minutes et reconstruit les
  ressources front-end verrouillées après la suite Python.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/services/maintenance.py`, `health.py` et `backups.py` ;
- commandes `run_fundboard_maintenance`, `fundboard_healthcheck`,
  `backup_fundboard`, `verify_fundboard_backup` et
  `restore_fundboard_sqlite` ;
- `Mizzac/FundBoard/view_modules/operations.py` et
  `templates/fundboard/operations.html` ;
- `Mizzac/Core/observability.py` et `middleware.py` ;
- `Mizzac/FundBoard/tests/test_operations.py` ;
- `Mizzac/FundBoard/migrations/0008_maintenancerun_connection_next_sync_index.py` ;
- `.github/workflows/ci.yml` ;
- quatre modèles d'unités sous `deploy/systemd/` ;
- `INSTALLATION.md`, `OPERATIONS.md`, `ADDING_CONNECTOR.md`,
  `SECURITY_AUDIT_PHASE_10.md` et présent rapport.

Modifications principales :

- modèles, administration, routes, navigation et accès aux cours de FundBoard ;
- réglages Django, `.env.example`, `.gitignore`, `README.md` ;
- documentation base, connecteurs et modèle canonique.

## 4. Migrations et impact sur les données

La migration `FundBoard.0008` :

- crée `MaintenanceRun`, son index utilisateur/date et la contrainte d'un seul
  passage `RUNNING` par utilisateur ;
- ajoute l'index `conn_user_next_sync_idx` sur
  `Connection(user, next_sync_at)`.

Elle ne modifie aucune valeur financière et ne lance aucun job. Elle a été
appliquée sur `/tmp/mizzac-phase10-fresh.sqlite3`. Cette base a ensuite été
sauvegardée, vérifiée et restaurée vers
`/tmp/mizzac-phase10-restored.sqlite3`. La base du dépôt n'a pas été modifiée.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `make ci` sous Django 6.1.1 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check` | aucun problème |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `pytest --cov --cov-report=term-missing` | 180 tests réussis ; couverture 82,43 % |
| `python3 -Wd -m pytest -q` | 180 tests et 89 sous-tests réussis, sans avertissement |
| `manage.py migrate --noinput` sur SQLite vierge | toutes les migrations appliquées, dont `FundBoard.0008` |
| `fundboard_healthcheck --json` sur base vierge | état `OK`, aucune migration en attente |
| sauvegarde puis `verify_fundboard_backup` | SHA-256 valide, 970 752 octets, 60 tables, 29 migrations |
| restauration vers une nouvelle SQLite puis healthcheck strict | restauration vérifiée et état `OK` |
| `manage.py check --deploy` avec HTTPS/cookies/HSTS/logs JSON | aucun problème |
| `pip check` dans un environnement isolé chargé avec les dépendances du projet | aucune dépendance cassée |
| `node --check` sur les scripts JavaScript | syntaxe valide |
| `EXPLAIN QUERY PLAN` sur les connexions dues | utilisation de `conn_user_next_sync_idx` |
| recherche statique de secrets et primitives dangereuses | aucun secret réel ni usage `shell=True` trouvé |
| version Django importée | `6.1.1` |
| `git diff --check` | aucune erreur d'espace ou marqueur de conflit |

Les 15 nouveaux tests couvrent tâches locales et réseau opt-in, échéances,
reprises, verrou, erreurs expurgées, actualisation des seuls instruments suivis,
sauvegarde, altération, vérification, restauration conservatrice, healthcheck,
isolation de la page, coût constant des requêtes, logs et en-têtes de sécurité.

## 6. Description des écrans concernés

- **Exploitation** affiche un bandeau `OK`, `WARNING` ou `ERROR`, quatre cartes
  de santé, les passages de maintenance et les synchronisations de connecteur.
- Les lignes exposent compteurs de snapshots, ordres, cours/change,
  connecteurs, statut public et identifiant de corrélation, sans payload ni
  secret.
- Le bouton **Lancer la maintenance locale** rappelle que le réseau est
  désactivé. Les synchronisations distantes restent accessibles depuis leur
  page ou le CLI explicitement configuré.
- Un lien **Exploitation** est ajouté à la navigation FundBoard.

Aucune capture automatisée n'a été produite. Le rendu, l'isolation utilisateur,
le POST protégé et la stabilité du nombre de requêtes sont testés avec le client
Django.

## 7. Risques, limites et dette technique restante

- La phase 10 clôt le plan initial, mais une CSP stricte reste à ajouter après
  extraction des scripts inline des templates.
- Le serveur WSGI/ASGI, TLS, pare-feu, limitation de débit, chiffrement disque et
  rotation des logs dépendent de l'hébergement choisi.
- La recherche de CVE exige une source externe actualisée. Les versions sont
  verrouillées et la CI vérifie leur cohérence, mais les mises à jour de sécurité
  restent une opération régulière à organiser sans dépasser Django 6.1.1.
- La vérification PostgreSQL confirme la lisibilité de l'archive ; une vraie
  restauration isolée reste indispensable avant de considérer la sauvegarde
  comme récupérable.
- Une maintenance multi-utilisateur appelle le change une fois par utilisateur.
  C'est sans impact pour l'usage personnel prévu ; une mutualisation serait utile
  pour une instance partagée.
- Les alertes restent locales (page, code retour, logs). Aucun courriel ou
  service tiers n'est configuré afin de ne pas divulguer de données.

## 8. Proposition exacte pour la suite

Le plan en dix phases est achevé. La suite recommandée est une période de
stabilisation :

1. installer le projet avec `INSTALLATION.md` sur la machine cible ;
2. exécuter une sauvegarde initiale et sa restauration de test ;
3. adapter puis activer les timers systemd, d'abord sans réseau ;
4. observer quelques passages, puis activer `--with-network` connecteur par
   connecteur ;
5. traiter seulement les anomalies réellement observées ;
6. avant toute exposition Internet, ajouter serveur de production, proxy HTTPS,
   CSP et analyse régulière des avis de sécurité.

## 9. Questions nécessitant validation

Aucune décision ne bloque un usage personnel local. L'activation effective des
timers et des appels réseau dépend de la machine cible et doit rester une action
explicite de votre part. Aucun timer système n'a été installé ou démarré par
cette phase.
