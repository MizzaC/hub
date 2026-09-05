# Rapport de phase 9 — Portefeuilles virtuels

Date de validation : 5 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`  
Version unique : Python 3.12 / Django 6.1.1

## 1. Résumé du résultat fonctionnel

La phase 9 est terminée. FundBoard possède une section **Portefeuilles
virtuels** entièrement séparée du patrimoine réel. Elle permet de créer un
capital et un cash fictifs, rechercher des instruments accessibles, construire
une watchlist puis passer des ordres virtuels `MARKET` ou `LIMIT`.

Le moteur prend en charge quantités entières ou fractionnaires selon le réglage
de la watchlist, frais fixes et proportionnels, spread, slippage, cash sans
marge, positions, PRU frais inclus, gains réalisés et latents, dividendes et
splits. Les ventes à découvert sont refusées.

La performance est historisée par snapshots et comparée à un benchmark dans un
graphique ApexCharts. Le journal expose cours, source, horodatage, retard, état
et motif d'un ordre ouvert ou rejeté. Les ordres ouverts peuvent être retraités
ou annulés. Le portefeuille peut être cloné, remis à zéro après confirmation,
archivé et exporté en JSON ou Excel.

## 2. Constats et décisions prises

- Les sept modèles virtuels ne référencent ni `Account`, ni `Position`, ni
  `Transaction`, ni `Connection`. Le moteur n'importe aucun connecteur et ne
  réalise aucun appel réseau.
- Une exécution sélectionne uniquement un `Price` positif, non erroné et dont
  `observed_at` est antérieur ou égal à l'instant d'exécution. Les données
  futures sont exclues au niveau de la requête.
- La devise du cours doit correspondre à la devise de base du portefeuille.
  Une exécution multidevise est refusée plutôt que convertie implicitement.
- Pour les titres non crypto, le cours doit avoir moins de 20 minutes et un état
  `REGULAR`. Pour les cryptomonnaies, la fenêtre est de 5 minutes et le marché
  est considéré ouvert 24/7.
- La moitié du spread et la totalité du slippage augmentent un achat ou
  diminuent une vente. Les montants sont arrondis au centime avec
  `ROUND_HALF_UP`, les prix à 12 décimales et les quantités à 18 décimales.
- Les détails du cours d'exécution sont copiés dans l'ordre et deviennent donc
  indépendants d'une actualisation future de la table `Price`.
- Les positions fermées sont conservées afin de ne pas perdre leurs gains
  réalisés ni leurs dividendes dans la performance cumulée.
- Le clonage repart de la valeur courante, copie positions et watchlist mais pas
  le journal. La remise à zéro conserve la watchlist et supprime uniquement le
  registre simulé.
- Les exports sont versionnés `1.0`, filtrés par propriétaire et neutralisent
  les chaînes interprétables comme formules Excel.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/services/paper_trading.py` ;
- `Mizzac/FundBoard/exports/paper_trading.py` ;
- `Mizzac/FundBoard/view_modules/paper_trading.py` ;
- `Mizzac/FundBoard/templates/fundboard/virtual_portfolios.html` ;
- `Mizzac/FundBoard/templates/fundboard/virtual_portfolio_detail.html` ;
- `Mizzac/FundBoard/templates/fundboard/modals/virtual_reset_confirm.html` ;
- `Mizzac/FundBoard/tests/test_paper_trading.py` ;
- `Mizzac/FundBoard/PAPER_TRADING_PHASE_9.md` ;
- `Mizzac/FundBoard/migrations/0007_phase9_paper_trading.py` ;
- présent rapport.

Modifications principales :

- `Mizzac/FundBoard/models.py`, `forms.py`, `admin.py` et `urls.py` ;
- navigation secondaire FundBoard ;
- modèle canonique et `README.md`.

## 4. Migrations et impact sur les données

La migration `FundBoard.0007` ajoute uniquement de nouvelles tables :

- `VirtualPortfolio` et `VirtualWatchlistEntry` ;
- `VirtualPosition`, `VirtualOrder` et `VirtualCashEvent` ;
- `VirtualCorporateAction` et `VirtualPortfolioSnapshot`.

Elle crée les contraintes de montants positifs, unicité portefeuille/instrument
et les index utilisateur, statut d'ordre, cash et snapshots. Elle ne transforme
ni ne supprime aucune table réelle. La migration a été appliquée intégralement
sur la base SQLite vierge `/tmp/mizzac-phase9-fresh.sqlite3`. La base du dépôt
n'a pas été modifiée.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `make ci` sous Django 6.1.1 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `pytest --cov --cov-report=term-missing` | 165 tests réussis ; couverture 83,25 % |
| `python3 -Wd -m pytest -q` | 165 tests et 89 sous-tests réussis, sans avertissement |
| `manage.py migrate --noinput` sur SQLite vierge | toutes les migrations appliquées, dont `FundBoard.0007` |
| `manage.py check --deploy` avec HTTPS, cookies sécurisés et HSTS | aucun problème |
| `node --check` sur `charts.js`, `currency.js` et le script de build | syntaxe valide |
| version Django importée | `6.1.1` |
| `git diff --check` | aucune erreur d'espace ou marqueur de conflit |

Les 16 nouveaux tests couvrent modèles et séparation structurelle, absence
d'appel réseau, anti-prix-futur, frais/spread/slippage, cours différés, limites,
horaires, fraîcheur, crypto 24/7, fractions, cash/position insuffisants, PRU,
gain réalisé après clôture, dividendes, splits, idempotence des événements,
benchmark, snapshots, clonage, remise à zéro, exports, injection Excel,
workflow HTTP et isolation utilisateur.

## 6. Description des écrans concernés

- **Portefeuilles virtuels** : avertissement de simulation, cartes synthétiques
  avec valeur, cash, positions, performance, fraîcheur et badge orange.
- **Détail virtuel** : cash, valeur, performance, gains, dividendes, hypothèses
  de frais, benchmark, courbe portefeuille/benchmark, positions avec PRU et
  fraîcheur, recherche, watchlist, journal des ordres, événements et registre de
  cash.
- Les ordres et titres affichent systématiquement « virtuel » ou « aucun ordre
  réel ». Un cours différé, manquant, hors séance ou trop ancien reste visible.
- Les formulaires modaux couvrent portefeuille, watchlist, ordre, événement,
  clonage, archivage et confirmation de remise à zéro.

Aucune capture automatisée n'a été produite. Le rendu des templates, les routes,
les exports et les permissions ont été validés avec le client Django.

## 7. Risques, limites et dette technique restante

- Les horaires reposent sur `market_state` et une fenêtre de fraîcheur ; ils ne
  modélisent pas jours fériés, enchères ou interruptions de cotation.
- Les ordres ouverts sont retraités manuellement. Une tâche planifiée pourra le
  faire en phase 10, toujours après l'arrivée d'un cours local horodaté.
- Il n'y a ni carnet d'ordres, ni liquidité, ni exécution partielle, ni marge,
  ni vente à découvert, ni fiscalité.
- Dividendes et splits sont saisis manuellement. La quantité prise en compte est
  celle détenue à l'application, sans reconstruction à une date historique.
- Une devise différente est refusée à l'exécution. L'affichage EUR/USD commun ne
  doit pas être confondu avec la devise comptable du registre virtuel.
- Le paper trading n'est pas un environnement de courtage, ne garantit aucune
  exécution réelle et ne constitue pas un conseil financier.

## 8. Proposition exacte pour la phase suivante

Exécuter la phase 10 sans modifier les garanties des phases précédentes :

1. planifier synchronisations, snapshots de patrimoine et traitement des ordres
   virtuels ouverts avec verrouillage et prévention des exécutions concurrentes ;
2. ajouter métriques, logs structurés expurgés, statuts d'exécution et alertes
   locales actionnables ;
3. automatiser et tester sauvegarde, vérification puis restauration SQLite et
   PostgreSQL ;
4. réaliser l'audit de sécurité final : secrets, permissions, CSRF, sessions,
   dépendances et surfaces de connecteur ;
5. profiler les vues principales, corriger les requêtes N+1 et valider les index ;
6. finaliser les guides installation, exploitation, import et ajout d'un
   connecteur.

## 9. Questions nécessitant validation

Aucune décision ne bloque l'utilisation locale de la phase 9. Avant une
éventuelle sophistication du moteur, il faudra seulement décider si vous
souhaitez conserver les horaires simplifiés ou intégrer un calendrier de marché
et si les événements de titres doivent rester manuels.

