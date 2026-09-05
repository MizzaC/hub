# Rapport Phase 1 — Stabilisation technique FundBoard / Mizzac

> Note de version : ce rapport conserve les résultats historiques de la phase 1.
> La version active du projet est désormais uniquement Django 6.1.1 ; l'ancienne
> matrice 5.2/6.1 et la trajectoire 6.2 ne font plus partie de la configuration.

Date : 4 septembre 2026  
Branche : `mizeos-FundBoard-test`

## 1. Résumé du résultat fonctionnel

La Phase 1 est implémentée. Le projet s'exécute désormais sur Django 5.2.17 LTS,
se configure par environnement et dispose d'une validation locale reproductible.
Les pages d'authentification et les principales pages FundBoard se rendent, les
modales sont authentifiées et isolées par propriétaire, et les régressions
visibles relevées en Phase 0 sont corrigées.

Les calculs d'abonnements et de conversion de devises n'utilisent plus de
`float`. Les soldes de devises différentes ne sont plus additionnés comme s'ils
étaient comparables. La suite contient 27 tests hermétiques et atteint 81,23 % de
couverture.

Django 6.2 n'étant pas encore publié, la production reste volontairement sur la
LTS 5.2. Une matrice Django 6.1.1 passe déjà intégralement et une feuille de route
datée prépare le passage vers Django 6.2 LTS.

## 2. Constats et décisions prises

- Django est verrouillé sur `5.2.17`, avec Python 3.12 comme référence.
- Les dépendances directes sont séparées entre runtime, développement,
  production PostgreSQL et matrice Django suivante. Les doublons `jsonfield` et
  la dépendance directe inutile à NumPy ont été supprimés.
- Les versions de Requests, Pillow, python-dotenv, pandas et des outils de test
  ont été actualisées et verrouillées.
- `SECRET_KEY` est obligatoire ; `DEBUG`, hôtes, CSRF, base, cookies, proxy, SSL
  et HSTS sont pilotés par variables typées. Les réglages de test restent
  hermétiques et sans secret externe.
- SQLite reste le défaut de développement. PostgreSQL utilise Psycopg 3 dans le
  groupe de production.
- L'inscription publique existante est conservée pour éviter une rupture
  fonctionnelle, dans l'attente d'une décision produit.
- La déconnexion est désormais un `POST` protégé par CSRF.
- Toutes les modales FundBoard exigent une session ; lecture, édition et
  suppression sont filtrées par utilisateur. La cohérence
  `Transaction.user == Transaction.account.user` est validée au niveau modèle.
- Les fréquences personnalisées exigent un nombre de jours positif. La
  normalisation annuelle est un service pur `Decimal`, arrondi au centime en
  `ROUND_HALF_UP` avec 365 occurrences quotidiennes, 52 hebdomadaires et 12
  mensuelles.
- Les données Chart.js sont produites par `json_script`. Chart.js reste
  temporairement sur CDN mais avec une version exacte ; son remplacement par un
  asset local est réservé à la Phase 2.
- Le convertisseur ToolBoard appelle un adaptateur borné par timeout, contrôle le
  statut HTTP et le payload, puis calcule en `Decimal`. Ses tests utilisent des
  mocks et ne font aucun appel réel.

## 3. Fichiers créés ou modifiés

### Socle et exploitation

- `.gitignore`, `.env.example`, `Makefile`, `pyproject.toml` ;
- `requirements.txt`, `requirements-base.txt`, `requirements-dev.txt`,
  `requirements-production.txt`, `requirements-django-next.txt` ;
- `README.md`, `OPERATIONS_DATABASE.md`, `DJANGO_6_2_UPGRADE.md` ;
- `Mizzac/Mizzac/settings.py`, `settings_test.py` et `urls.py`.

### Application et interface

- templates communs de base, login, inscription et navbar dans `DashBoard` ;
- modèles, formulaires, vues, routes et templates FundBoard concernés par les
  comptes, transactions, abonnements, revenus, portefeuille et dashboard ;
- nouveau service `FundBoard/services/recurring.py` ;
- nouveau style partagé minimal `DashBoard/static/css/styles.css` et correction
  du chemin statique GameBoard ;
- nouveau service `ToolBoard/services/currency.py` et adaptation de sa vue ;
- nettoyage Ruff des imports existants dans les cinq applications.

### Tests

- `DashBoard/tests/test_auth.py` et `test_smoke.py` ;
- `FundBoard/tests/test_models.py`, `test_recurring_service.py` et
  `test_views.py` ;
- `ToolBoard/test_currency.py`.

## 4. Migrations et impact sur les données

Aucun fichier de migration n'a été créé, modifié ou réécrit. Aucune base
utilisateur n'a été ouverte ni migrée. Une migration complète a uniquement été
exécutée sur une base SQLite neuve sous `/tmp`, avec succès.

Le danger de `FundBoard.0005` sur une base historique reste entier : une base
peuplée arrêtée en `0001`–`0004` ne doit pas lancer `migrate`. La procédure de
sauvegarde, restauration et diagnostic est documentée. La correction de cette
migration ou un import de récupération attend obligatoirement l'état de la base
réelle et une sauvegarde vérifiée.

Les validations ajoutées aux modèles ne changent pas le schéma. La cohérence de
transaction est applicative à ce stade ; une écriture ORM qui contourne
`full_clean()` peut encore la contourner. Une contrainte et un service d'écriture
seront traités avec le modèle canonique en Phase 3.

## 5. Commandes de validation exécutées

| Contrôle | Résultat |
|---|---|
| `make ci` sous Python 3.12 / Django 5.2.17 | succès |
| Ruff | 0 erreur |
| `compileall` | succès |
| `manage.py check` | 0 problème |
| `makemigrations --check --dry-run` | aucune modification détectée |
| pytest + couverture | 27 tests réussis, 81,23 % |
| pytest avec `-Wd` sous Django 5.2.17 | 27 tests, aucun avertissement |
| pytest avec `-Wd` sous Django 6.1.1 | 27 tests, 81,23 %, aucun avertissement |
| `manage.py check --deploy` avec réglages HTTPS/SQLite | 0 problème |
| `manage.py check --deploy` avec backend PostgreSQL/Psycopg | 0 problème, sans connexion à une base |
| migration complète d'une SQLite neuve sous `/tmp` | toutes les migrations appliquées |
| `git diff --check` | aucune erreur d'espacement |

Les dépendances de validation ont été installées uniquement sous `/tmp` ; aucun
environnement virtuel ou artefact de base n'a été ajouté au dépôt.

## 6. Écrans concernés

Aucune refonte graphique n'a été faite avant la Phase 2. Les rendus ont été
vérifiés avec le client Django et des données factices :

- login et inscription s'affichent à nouveau sur le layout commun ;
- la navbar déconnecte via un formulaire POST ;
- le dashboard FundBoard affiche les soldes groupés par devise et les dernières
  transactions avec la devise de leur compte ;
- les comptes acceptent et affichent un code devise ISO normalisé ;
- le portefeuille possède une page de compatibilité fonctionnelle ;
- les abonnements affichent leurs équivalents mensuel/annuel et un graphique aux
  données JSON sûres, y compris pour une fréquence personnalisée ;
- les revenus utilisent les vrais champs du modèle ;
- les modales affichent leurs erreurs et refusent les accès anonymes ou croisés ;
- le convertisseur ToolBoard conserve son écran et retourne une erreur maîtrisée
  si le fournisseur est indisponible.

## 7. Risques, limites et dette restante

1. La base déployée, son état de migration et ses sauvegardes ne sont toujours
   pas connus. C'est le seul risque critique bloquant toute migration métier.
2. `FundBoard.0005` reste destructive pour une base historique ; elle n'a
   volontairement pas été réécrite.
3. L'interface utilise encore Bootstrap et des CDN. Les assets Tabler locaux et
   l'unification des graphiques appartiennent à la Phase 2.
4. Les tests caractérisent le socle et FundBoard, mais les imports SkyJo, les
   autres outils ToolBoard et les templates de jeux incomplets ont encore une
   couverture faible.
5. La matrice 6.1 anticipe 6.2, mais ne peut pas garantir la compatibilité avec
   une version 6.2 qui évolue encore avant sa sortie du 6 avril 2027.
6. Les contraintes financières, l'idempotence, les imports et les connecteurs
   seront testés avec leurs implémentations dans les Phases 3 à 6.

## 8. Proposition exacte pour la Phase 2

1. Ajouter l'application `Core` sans déplacer de données ni modifier les routes.
2. Installer `@tabler/core` sous version exacte via npm et lockfile, conserver sa
   licence, puis servir CSS, JS, icônes et graphiques localement.
3. Créer un unique layout `Core` avec blocs documentés, messages, navbar,
   sidebar et composants d'état vide/erreur.
4. Migrer d'abord login, inscription et accueil, puis FundBoard page par page en
   préservant les modales et noms de routes.
5. Migrer une page de GameBoard, DrunkBoard et ToolBoard comme smoke test.
6. Retirer les doubles chargements Bootstrap et tous les CDN lorsque chaque page
   dépendante est migrée.
7. Étendre les tests de rendu pour vérifier héritage, assets locaux, navigation
   active, formulaires, modales et responsive de base.

La Phase 2 ne doit créer aucune migration métier et ne doit pas commencer la
récupération de `0005` sans le préflight de base.

## 9. Questions nécessitant validation

1. Où se trouve la base réellement utilisée, quel est son moteur, et quelle est
   la sortie de `showmigrations FundBoard` ?
2. Existe-t-il une sauvegarde antérieure à `FundBoard.0005`, et sa restauration
   a-t-elle déjà été testée ?
3. L'inscription doit-elle rester publique ou être remplacée par la création de
   comptes par un administrateur ?
4. La Phase 2 Tabler décrite ci-dessus peut-elle commencer ?
