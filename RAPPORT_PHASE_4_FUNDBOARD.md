# Rapport de phase 4 — Saisie, imports et exports

Date de validation : 4 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`  
Version unique : Python 3.12 / Django 6.1.1

## 1. Résumé du résultat fonctionnel

La phase 4 est terminée. Un utilisateur authentifié peut gérer sans connecteur
externe ses comptes, instruments privés ou partagés, positions, transactions,
biens immobiliers et prêts depuis l'interface Tabler. Les suppressions
financières ambiguës ont été remplacées par des archivages ou annulations qui
conservent l'historique.

La page **Imports / exports** fournit des modèles JSON et Excel versionnés 1.0,
une prévisualisation sans écriture, l'import, l'historique des lots, le rapport
d'erreurs téléchargeable, l'annulation prudente d'un lot et les exports JSON,
Excel ou CSV.

Conformément à la décision utilisateur, l'import applique un **succès partiel
par ligne** : une ligne invalide est entièrement annulée et n'est jamais
importée ; les autres lignes continuent d'être traitées et validées. Cette règle
est identique pour JSON et Excel et s'applique aussi aux contraintes de base de
données.

Le projet utilise désormais uniquement Django 6.1.1. La matrice Django 5.2 /
Django-next et la trajectoire 6.2 ont été retirées de la configuration active.

## 2. Constats et décisions prises

- La base étant déclarée sans données réelles, la phase 4 prolonge le schéma
  canonique neuf sans migration de reprise de l'ancien prototype.
- Les références personnelles sont stables et privées par utilisateur. Elles
  relient les feuilles sans exposer de clé technique ou fournisseur.
- L'ordre d'exécution est comptes, instruments, prêts, positions, transactions,
  immobilier, quel que soit l'ordre du document.
- Chaque ligne s'exécute dans une transaction avec point de sauvegarde. Une
  erreur de type, de relation, de propriété, de modèle ou de contrainte SQL
  annule uniquement cette ligne.
- Le dry-run appelle exactement le même moteur, puis annule toutes ses
  écritures.
- L'empreinte SHA-256 du fichier empêche un double import actif. Les
  transactions utilisent en plus une clé d'idempotence fournie ou déterministe.
- L'annulation utilise un contrôle optimiste : elle refuse tout le retour
  arrière si un objet a été modifié/supprimé depuis l'import ou si une nouvelle
  donnée dépendante rend l'opération ambiguë.
- Le fichier importé brut n'est pas conservé. Seuls son nom, son format, son
  empreinte, ses compteurs, ses erreurs et les champs financiers nécessaires à
  l'annulation sont enregistrés.
- Les exports excluent secrets, tokens, cookies, références de secrets,
  `metadata`, identifiants fournisseur et données d'autres utilisateurs.
- Les formules entrantes sont refusées. Macros, liens externes et archives
  Excel disproportionnées sont bloqués ; les cellules textuelles dangereuses
  des exports sont neutralisées.
- Une piste d'audit séparée enregistre créations, modifications, archivages,
  imports, annulations et exports sans copier les valeurs financières ou le
  contenu des fichiers.
- Une dette immobilière dans une autre devise n'est pas soustraite directement :
  l'interface indique qu'une conversion est requise.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/imports/schema.py`, `parser.py`, `templates.py` et
  `service.py` : schéma 1.0, lecture sécurisée, modèles et moteur transactionnel ;
- `Mizzac/FundBoard/exports/service.py` : exports complets ou par ressource ;
- `Mizzac/FundBoard/view_modules/manual.py` : CRUD et archivages manuels ;
- `Mizzac/FundBoard/view_modules/data_transfer.py` : dry-run, import, rapports,
  annulation, modèles et téléchargements ;
- `Mizzac/FundBoard/services/audit.py` : piste d'audit financière minimale ;
- templates `instruments.html`, `real_estate.html`, `loans.html`,
  `import_export.html`, `import_batch.html`, `modals/model_form.html` et
  `modals/archive_confirm.html` ;
- `Mizzac/FundBoard/tests/test_imports_exports.py` et
  `test_manual_crud.py` ;
- `Mizzac/FundBoard/IMPORT_EXPORT_V1.md` et présent rapport.

Modifications principales :

- `Mizzac/FundBoard/models.py` : références et statuts manuels, `Loan`,
  `RealEstate`, `RealEstateValuation`, `PrivateEquityHolding`, `ImportBatch`,
  `ImportIssue`, `ImportChange` et `FinancialAuditEvent` ;
- `Mizzac/FundBoard/forms.py`, `views.py`, `urls.py` et `admin.py` : formulaires
  scopés, routes, permissions, archivage et administration ;
- navigation et écrans comptes, portefeuille et transactions : actions de
  création, modification, archivage et annulation ;
- `requirements-base.txt` : ajout d'`openpyxl==3.1.5` ;
- `requirements.txt` : verrouillage exclusif de `Django==6.1.1` ;
- `README.md`, `DJANGO_VERSION.md` et `MODELE_CANONIQUE.md` : procédures et
  choix courants ;
- rapports des phases 1 à 3 : note signalant que leurs résultats Django 5.2
  sont historiques.

Suppressions :

- `requirements-django-next.txt` et `DJANGO_6_2_UPGRADE.md`, devenus
  contradictoires avec le choix exclusif de Django 6.1.1.

## 4. Migrations et impact sur les données

La migration
`FundBoard.0002_financialauditevent_importbatch_importchange_and_more` ajoute
les entités et contraintes de phase 4 ainsi que les champs de référence/statut
aux comptes, instruments et positions.

Elle a été générée depuis l'état final des modèles, puis appliquée avec succès
sur une base SQLite vierge dans `/tmp`. La base locale du dépôt n'a pas été
modifiée.

Cette branche reste volontairement destinée à une base neuve :
`FundBoard.0001_initial` avait déjà remplacé l'ancien prototype en phase 3. Si
une base historique apparaît, il ne faut pas appliquer ces migrations dessus ;
il faudra l'archiver et construire une reprise dédiée.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `make ci` sous Django 6.1.1 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `pytest --cov --cov-report=term-missing` | 75 tests et 72 sous-tests réussis ; couverture 83,79 % |
| `python3 -Wd -m pytest -q` | 75 tests réussis, aucun avertissement de dépréciation |
| `manage.py migrate --noinput` sur `/tmp/mizzac-phase4-final.sqlite3` | toutes les migrations appliquées, dont `FundBoard.0002` |
| `manage.py check --deploy` avec réglages HTTPS | aucun problème |
| `git diff --check` | aucune erreur d'espace ou marqueur de conflit |

Les tests ajoutés couvrent notamment le succès partiel, les erreurs de parsing
et de modèle, le dry-run, les doublons, l'annulation et son refus prudent, les
modèles téléchargeables, le rejet de formules, l'isolation entre deux
utilisateurs, les exports sans charges sensibles, l'audit et les permissions
des modales.

## 6. Description des écrans concernés

- **Comptes** : formulaire enrichi, référence personnelle, devise, quote-part,
  IBAN déjà masqué, statut et archivage conservant l'historique.
- **Instruments** : référentiel visible pour l'utilisateur, distinction entre
  instrument partagé en lecture seule et instrument privé modifiable.
- **Portefeuille** : ajout/modification/archivage des positions depuis les
  cartes de comptes d'investissement.
- **Transactions** : ajout, modification et annulation, avec conservation de la
  ligne dans l'historique filtrable.
- **Immobilier** : cartes de valeur brute, quote-part, capital restant dû et
  valeur nette, avec valorisation datée et alerte de conversion inter-devise.
- **Prêts** : capital initial/restant, type, taux, assurance et échéance.
- **Imports / exports** : zone d'upload, boutons dry-run/import, modèles JSON et
  Excel, sélection de ressource et de format, puis dix derniers lots.
- **Détail d'un lot** : compteurs, erreurs feuille/ligne/colonne, CSV d'erreurs
  et bouton d'annulation tant que le lot n'est pas déjà annulé.

Aucune capture automatisée n'a été produite. Les écrans et modales ont été
validés par le client de test Django, avec assertions d'authentification,
d'isolation et de contenu.

## 7. Risques, limites et dette technique restante

- Le schéma d'import 1.0 n'a pas encore de mécanisme de migration automatique
  vers une future version 2.0.
- Le filtre d'export actuel choisit une catégorie de données ; les filtres par
  date, compte ou statut pourront être ajoutés lorsqu'un besoin réel sera fixé.
- L'annulation est volontairement stricte. Une simple modification postérieure
  oblige à corriger manuellement ou à importer un nouveau fichier plutôt qu'à
  risquer d'écraser une donnée récente.
- `PrivateEquityHolding` prépare la modélisation, mais son interface détaillée,
  les appels de fonds et distributions restent dans le périmètre spécialisé de
  la phase 7.
- Les prêts sont suivis comme passifs ; le simulateur et le tableau
  d'amortissement appartiennent également à la phase 7.
- Les valorisations restent manuelles/importées. Aucun cours, change ni
  connecteur externe n'a été ajouté en phase 4.
- Le dashboard consolidé ne doit pas additionner des devises différentes sans
  taux datés ; cette intégration relève de la phase 5.
- SQLite reste réservé au développement ; PostgreSQL est recommandé en
  production pour la précision numérique et la concurrence.

## 8. Proposition exacte pour la phase suivante

Exécuter la phase 5 dans cet ordre :

1. définir l'interface `MarketDataProvider` et un fournisseur manuel/local de
   référence, testable sans réseau ;
2. introduire le cache, la fraîcheur, les erreurs et l'historique de collecte ;
3. faire valider explicitement les fournisseurs externes avant toute dépendance
   réseau, en documentant coût, quotas, licence et limites ;
4. alimenter `Price` et `ExchangeRate` de manière idempotente, sans qu'un calcul
   financier ne déclenche lui-même un appel réseau ;
5. créer les snapshots et le dashboard patrimonial synthétique avec devise de
   référence et taux datés explicites ;
6. ajouter les pages de détail, statuts de fraîcheur et commandes manuelles de
   synchronisation ;
7. terminer par les tests de contrats mockés, cache, taux manquants, données
   périmées, permissions et absence de réseau dans la suite standard.

## 9. Questions nécessitant validation

Aucune décision supplémentaire n'est requise pour utiliser la phase 4.

Avant la phase 5, deux choix fonctionnels devront être validés : la devise de
référence du dashboard et l'autorisation éventuelle de fournisseurs externes de
cours/change. Aucun fournisseur ne sera intégré silencieusement.
