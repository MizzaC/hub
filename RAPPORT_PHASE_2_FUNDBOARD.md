# Rapport de phase 2 — Socle UI Tabler partagé

> Note de version : les mentions de Django 5.2 ci-dessous décrivent des tests
> historiques. La seule version active du projet est désormais Django 6.1.1.

Date de validation : 4 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`

## 1. Résumé du résultat fonctionnel

La phase 2 est terminée. Mizzac dispose maintenant d'un socle d'interface
commun dans l'application Django `Core`. La navigation principale,
l'authentification, l'accueil et les pages principales de DashBoard,
FundBoard, GameBoard, ToolBoard et DrunkBoard utilisent toutes le même layout
Tabler responsive.

FundBoard conserve sa navigation secondaire et ses modales asynchrones. Ses
pages vue d'ensemble, portefeuille, comptes, transactions, abonnements et
revenus ont été migrées vers les composants Tabler. Les routes existantes et
les contrôles d'accès restent couverts par les tests.

Les assets sont servis localement : aucune ressource CDN n'est nécessaire dans
le navigateur. Le thème clair/sombre est appliqué avant le rendu visuel et le
choix est conservé dans le stockage local du navigateur.

## 2. Constats et décisions prises

- `@tabler/core` est verrouillé en version `1.4.0`, dernière version stable
  vérifiée au début de la phase sur les publications officielles de Tabler.
- `@tabler/icons` est verrouillé en `3.46.0` et seules les quinze icônes
  réellement utilisées sont copiées dans Django.
- Chart.js `4.4.7` reste l'unique bibliothèque de graphiques pendant la
  migration. ApexCharts n'a pas été ajouté, afin d'éviter le doublon demandé
  par le plan.
- Les distributions, leurs empreintes npm et leurs licences sont conservées
  avec le dépôt. `package-lock.json` rend l'installation reproductible.
- Node.js 20 ou plus récent est la version front de référence, matérialisée par
  `.nvmrc` et `package.json`, car Tabler 1.4 l'exige.
- Le layout expose les blocs stables `title`, `body_class`, `page_header`,
  `content`, `extra_css` et `extra_js`.
- `common/base.html` est gardé comme façade de compatibilité très mince. Les
  anciens écrans qui l'étendent bénéficient donc immédiatement de `Core` sans
  rupture de template.
- Les pages FundBoard séparent les montants par devise. Aucun total financier
  trompeur n'est produit avant l'introduction des taux de change et snapshots.
- Le graphique des abonnements reçoit ses données via `json_script`; aucune
  chaîne JSON applicative n'est injectée directement dans JavaScript.

Références des versions retenues :

- <https://github.com/tabler/tabler/releases/tag/v1.4.0>
- <https://www.npmjs.com/package/@tabler/core/v/1.4.0>
- <https://www.npmjs.com/package/@tabler/icons/v/3.46.0>

## 3. Fichiers créés ou modifiés

Principaux ajouts :

- `Mizzac/Core/` : application, layout, messages, feuilles de style, gestion
  du thème, icônes, distributions tierces et tests de smoke UI ;
- `package.json`, `package-lock.json`, `.nvmrc` : dépendances front verrouillées
  et version Node de référence ;
- `scripts/build_frontend.mjs` et `scripts/vendor-licenses/` : reconstruction
  déterministe des assets Django et conservation des licences ;
- `Mizzac/FundBoard/templates/fundboard/portfolio.html` : page portefeuille
  alignée sur le nouveau socle ;
- `RAPPORT_PHASE_2_FUNDBOARD.md` : présent compte rendu.

Principales modifications :

- `Mizzac/Mizzac/settings.py` : activation de `Core` ;
- `Mizzac/DashBoard/templates/common/`, `templates/pages/dashboard.html`,
  `forms.py` et `urls.py` : compatibilité, accueil et authentification Tabler ;
- `Mizzac/FundBoard/templates/fundboard/`, `static/FundBoard/style.css` et
  `views.py` : navigation secondaire, pages détaillées, modales et contextes ;
- `Mizzac/GameBoard/templates/pages/gameboard.html`,
  `static/GameBoard/style.css` et `views.py` : page de smoke test complète ;
- `Mizzac/ToolBoard/templates/pages/toolboard.html` et `views.py` : catalogue
  d'outils partagé et correction des liens par slug ;
- `Mizzac/DrunkBoard/templates/pages/drunkboard.html` : état vide partagé ;
- `README.md` et `Makefile` : procédure de reconstruction et validation locale.

## 4. Migrations et impact sur les données

Aucune migration de schéma ni de données n'a été ajoutée pendant la phase 2.
Les changements sont limités à l'interface, aux ressources statiques et aux
contextes de vues nécessaires au rendu.

Comme confirmé par le propriétaire du projet, aucune base réelle n'est à
préserver. Une base SQLite entièrement neuve a donc été créée dans `/tmp` et
toutes les migrations existantes, y compris `FundBoard.0005`, s'y appliquent
avec succès. La base du dépôt n'a pas été modifiée.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `npm ci --ignore-scripts --no-audit --no-fund` | 6 paquets installés depuis le lockfile ; avertissement attendu avec le Node 18 local, Node 20 étant requis pour l'environnement de référence |
| `npm run build:assets` | 36 assets versionnés copiés avec succès |
| `python3 -m ruff check Mizzac` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `manage.py makemigrations --check --dry-run --settings=Mizzac.settings_test` | aucun changement détecté |
| `manage.py migrate --noinput` sur une SQLite neuve dans `/tmp` | toutes les migrations appliquées |
| `manage.py check --deploy` avec réglages HTTPS de production | aucun problème |
| `pytest --cov --cov-report=term-missing` sous Django 5.2.17 | 34 tests et 59 sous-tests réussis ; couverture totale 82,91 % |
| `python3 -Wd -m pytest -q` sous Django 6.1.1 | 34 tests et 59 sous-tests réussis, sans avertissement de dépréciation |
| `make ci` avec l'environnement Django 5.2.17 | chaîne locale complète réussie |
| `git diff --check` | aucune erreur d'espace ou de conflit |

Les tests UI vérifient notamment l'héritage du layout commun, les assets
locaux, les versions verrouillées, les licences collectables, la navigation
active, les contrôles responsive et de thème, l'authentification, Chart.js
local et l'absence de l'ancien Bootstrap.

## 6. Description des écrans concernés

- **Navigation commune** : barre supérieure compacte avec identité Mizzac,
  accès aux cinq applications, indication de la section active, menu utilisateur
  et bascule clair/sombre. Sur petit écran, la navigation est repliable.
- **Connexion et inscription** : cartes centrées, champs Tabler, labels
  explicites, aides et erreurs visibles, liens d'action et icônes cohérents.
- **Accueil** : bandeau de bienvenue puis quatre cartes d'accès direct aux
  principales applications.
- **FundBoard — aperçu** : bandeau des soldes séparés par devise, quatre cartes
  de synthèse, dernières transactions et état honnête de la qualité des données.
- **FundBoard — détails** : navigation latérale sur grand écran et repliable sur
  mobile ; tableaux responsive pour comptes, portefeuille, transactions,
  abonnements et revenus ; états vides explicites.
- **Modales FundBoard** : création, édition, suppression et choix de source
  chargés sans rechargement complet, avec retour d'erreur accessible.
- **GameBoard, ToolBoard et DrunkBoard** : pages d'entrée homogènes servant de
  smoke tests réels du layout commun.

Aucune capture pixel n'a été automatisée dans cette phase ; la validation
porte sur le rendu Django, la structure HTML, l'accessibilité essentielle et
les comportements couverts par la suite de tests.

## 7. Risques, limites et dette technique restante

- Le poste courant utilise Node 18.19.1 alors que Tabler 1.4 déclare Node 20
  minimum. La copie des distributions précompilées fonctionne, mais toute
  reconstruction officielle doit utiliser Node 20 ou plus récent.
- La préférence de thème est persistante par navigateur, mais n'est pas encore
  synchronisée entre appareils dans le compte Django. Une préférence serveur
  demanderait un profil utilisateur et une migration de données.
- Le dashboard patrimonial complet (patrimoine net, passifs, allocation,
  performance, benchmark et fraîcheur des connexions) dépend du modèle
  canonique et des snapshots prévus aux phases 3 et 5. La page actuelle évite
  volontairement d'inventer ces indicateurs.
- Chart.js est conservé temporairement. La décision de le garder ou de le
  remplacer ne devra être prise qu'après les graphiques financiers réels et
  une validation visuelle.
- Les tests contrôlent la structure et le rendu serveur, mais pas encore les
  interactions dans un navigateur réel ni la comparaison visuelle automatisée.

## 8. Proposition exacte pour la phase suivante

Passer à la phase 3 par incréments non destructifs sur une base neuve :

1. figer les invariants de devises, décimales, propriété utilisateur et
   idempotence dans des tests ;
2. introduire `Institution`, `Connection`, `ExternalIdentifier`, `Instrument`,
   `Position`, `Transaction` enrichie, `Price`, `ExchangeRate` et `Snapshot` ;
3. générer des migrations initiales cohérentes sans couche de reprise des
   anciennes données, puisque la base repart de zéro ;
4. ajouter les services purs de conversion, valorisation, patrimoine net et
   performance avec cas connus et arrondis testés ;
5. adapter FundBoard au nouveau modèle derrière des requêtes strictement
   filtrées par utilisateur ;
6. terminer par une migration fraîche, les tests de permissions et la matrice
   Django 5.2/6.1.

## 9. Questions nécessitant validation

Aucune question ne bloque la clôture de la phase 2.

Avant d'ouvrir la phase 3, une seule décision fonctionnelle est utile : valider
que l'ancien modèle FundBoard peut être remplacé directement, sans écrire de
migration de reprise ni conserver de façade pour une base historique. Cette
option est cohérente avec la confirmation qu'il n'existe aucune donnée réelle.
