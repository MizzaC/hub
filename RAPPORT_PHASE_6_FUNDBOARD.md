# Rapport de phase 6 — Connecteurs financiers en lecture seule

Date de validation : 5 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`  
Version unique : Python 3.12 / Django 6.1.1

## 1. Résumé du résultat fonctionnel

La phase 6 est terminée avec un socle commun de connexions financières en
lecture seule. FundBoard sait désormais configurer, tester, synchroniser et
déconnecter une source depuis une nouvelle section **Connexions**, sans placer
de secret dans la base. Chaque exécution est idempotente, incrémentale lorsque
le fournisseur le permet, isolée par utilisateur et visible avec son statut et
ses compteurs expurgés.

Quatre parcours sont disponibles :

- comptes bancaires français/européens via Enable Banking et un consentement
  AIS limité aux propres comptes de l'utilisateur ;
- soldes, positions et trades Binance Spot avec contrôle obligatoire d'une clé
  sans trading et sans retrait ;
- positions et opérations Ledger Live par import CSV local, sans seed ni clé
  privée ;
- opérations Trade Republic par import JSON/CSV expérimental, sans PIN, 2FA,
  cookie ou API privée.

Une donnée ou ligne invalide est entièrement ignorée. Les autres éléments
valides sont enregistrés, et le run devient `PARTIAL` avec un compteur de
rejets. Les pages `GET`, imports locaux et tests n'effectuent aucun appel
réseau.

## 2. Constats et décisions prises

- Le site officiel Powens Wealth cite bien Finary comme client. Powens annonce
  plus de 1 800 institutions et une sandbox limitée à 50 connexions, mais son
  passage en production exige un contrat et aucun tarif public adapté à un
  projet personnel n'a été trouvé.
- Enable Banking est retenu comme premier `OpenBankingProvider`. Sa
  documentation prévoit une application de production restreinte aux propres
  comptes d'un particulier et ses conditions rendent gratuit l'usage de son
  Control Panel/API dans ce périmètre. Ce choix évite d'introduire silencieusement
  une offre payante.
- GoCardless Bank Account Data et Bridge restent des alternatives documentées,
  mais leurs conditions/tarifs de production devront être revalidés avant une
  implémentation. Le contrat interne permet de remplacer Enable Banking sans
  modifier les données canoniques.
- Le flux bancaire utilise `state`, JWT RS256, redirection de consentement,
  session AIS, comptes, soldes, transactions et pagination. La reprise
  incrémentale part de la dernière date enregistrée.
- Le client Binance n'expose que `GET`, corrige la dérive d'horloge, utilise
  HMAC-SHA256, `recvWindow=5000`, timeouts et retry/backoff sur 429/5xx. Les
  trades sont paginés par `fromId`.
- Les valeurs financières deviennent des `Decimal` à la frontière des
  adaptateurs. USDT, USDC et FDUSD sont normalisés en USD pour la contre-valeur,
  tandis que l'actif de règlement et les frais exacts restent identifiés dans
  les métadonnées.
- Le scraper Trade Republic fourni a seulement servi à comprendre son format
  d'export. Son authentification téléphone/PIN/2FA et son WebSocket privé n'ont
  pas été copiés. Le feature flag live reste désactivé.
- Les secrets sont résolus depuis des noms d'environnement autorisés. La base
  stocke uniquement `env:binance` ou `env:enable_banking`, jamais leur valeur.
- Une commande explicite est fournie pour cron/systemd ; aucun scheduler lourd
  n'est introduit dans ce projet personnel.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/integrations/connectors/` : contrat, registre, résolution
  des secrets, adaptateurs Binance, Enable Banking et imports locaux ;
- `Mizzac/FundBoard/services/connectors.py` : cycle de synchronisation,
  persistance idempotente, succès partiel, test et déconnexion ;
- `Mizzac/FundBoard/view_modules/connectors.py` : vues authentifiées, actions
  POST/CSRF et callback bancaire ;
- `Mizzac/FundBoard/templates/fundboard/connections.html` et
  `connection_detail.html` : configuration, statut, actions, comptes et runs ;
- `Mizzac/FundBoard/management/commands/sync_financial_connections.py` : point
  d'entrée de planification ;
- `Mizzac/FundBoard/tests/test_connectors.py` : contrats mockés, sécurité,
  pagination, idempotence, imports et vues ;
- `Mizzac/FundBoard/CONNECTORS.md` : choix fournisseur, configuration, limites
  et exploitation ;
- `Mizzac/FundBoard/migrations/0004_connection_configuration_and_more.py` ;
- présent rapport.

Modifications principales :

- `Mizzac/FundBoard/models.py`, `admin.py`, `forms.py` et `urls.py` ;
- navigation FundBoard et modale de choix de source de compte ;
- `Mizzac/FundBoard/MODELE_CANONIQUE.md` et `README.md` ;
- `.env.example` et `Mizzac/Mizzac/settings.py` ;
- `requirements-base.txt`, avec `PyJWT[crypto]==2.13.0` et
  `cryptography==50.0.1`.

## 4. Migrations et impact sur les données

La migration `FundBoard.0004_connection_configuration_and_more` :

- ajoute à `Connection` la configuration non secrète, la date du dernier test
  et l'expiration du consentement ;
- crée `ConnectorSyncRun` avec déclencheur, statut, curseurs, compteurs,
  messages publics et UUID de corrélation ;
- impose une seule synchronisation `RUNNING` par connexion ;
- ajoute les événements d'audit création/test/sync/déconnexion.

La migration a été générée sous Django 6.1.1 et appliquée avec succès sur la
base SQLite vierge `/tmp/mizzac-phase6-fresh.sqlite3`. La base du dépôt n'a pas
été modifiée. La stratégie validée reste un démarrage depuis une base neuve.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `make ci` sous Django 6.1.1 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `pytest --cov --cov-report=term-missing` | 118 tests et 86 sous-tests réussis ; couverture 80,26 % |
| `python3 -Wd -m pytest -q` | 118 tests et 86 sous-tests réussis, sans avertissement |
| `manage.py migrate --noinput` sur SQLite vierge | toutes les migrations appliquées, dont `FundBoard.0004` |
| `manage.py check --deploy` avec réglages HTTPS | aucun problème |
| `node --check` sur `charts.js` et `currency.js` | syntaxe valide |
| import de `django`, `jwt` et `cryptography` | versions verrouillées compatibles |
| `git diff --check` | aucune erreur d'espace ou marqueur de conflit |

Les appels Binance et Enable Banking sont totalement simulés dans la suite. Les
tests couvrent pagination, curseurs, nombres décimaux, permission Binance
dangereuse, retry 429, consentement bancaire personnel, masquage IBAN,
idempotence, concurrence, erreur expurgée, ligne invalide ignorée, conservation
de l'historique, ownership, POST/CSRF et absence de réseau sur `GET`.

## 6. Description des écrans concernés

- **Connexions** : liste limitée à l'utilisateur, fournisseur, institution,
  nom, statut et formulaire de création contextuel.
- **Création Enable Banking** : banque ASPSP, pays et durée demandée du
  consentement, sans champ de mot de passe bancaire.
- **Création Binance** : liste de paires et avertissement sur les permissions
  interdites, sans champ de clé API.
- **Création Ledger / Trade Republic** : avertissements de confidentialité et
  acceptation explicite du caractère expérimental de Trade Republic.
- **Détail connexion** : dernier test, dernière synchronisation, expiration du
  consentement, boutons autoriser/tester/synchroniser/déconnecter, comptes
  créés et 20 derniers runs.
- **Ajout de compte** : lien direct vers les sources bancaires, Binance, Ledger
  et Trade Republic, tout en conservant l'ajout manuel.

Aucune capture automatisée n'a été produite. Les templates, routes, permissions
et contenus ont été validés avec le client Django.

## 7. Risques, limites et dette technique restante

- Aucun compte bancaire ou Binance réel n'a été contacté : l'activation finale
  nécessite que l'utilisateur crée ses propres clés, place les secrets hors du
  dépôt et donne son consentement. Les tests valident le contrat mocké, pas la
  disponibilité réelle de chaque banque.
- Les conditions et gratuités d'Enable Banking peuvent évoluer. Un usage
  public, partagé ou commercial sortirait du mode personnel restreint et
  imposerait une nouvelle vérification contractuelle.
- Les données patrimoniales sont sensibles. FundBoard ne chiffre pas chaque
  champ applicatif : le chiffrement du disque, des sauvegardes et du transport
  HTTPS reste une responsabilité de déploiement.
- Binance synchronise actuellement Spot, soldes et trades configurés. Dépôts,
  retraits on-chain, conversions, earn/rewards et staking restent à ajouter.
  Une clé Binance doit être révoquée aussi sur Binance après déconnexion locale.
- Assimiler USDT/USDC/FDUSD à USD convient à l'affichage patrimonial courant,
  mais ne représente pas une garantie permanente de parité.
- Ledger fonctionne par export CSV. Le suivi BTC/ETH/ERC-20 par adresse/xpub
  n'est pas encore branché, car il nécessite le choix explicite d'un fournisseur
  blockchain et comporte un risque de confidentialité.
- Trade Republic ne synchronise aucun endpoint privé et dépend des champs
  réellement présents dans l'export. Une évolution de format pourra demander
  un nouveau mapper.
- La planification repose sur cron/systemd et non sur une file Celery. Il n'y a
  ni webhook bancaire ni actualisation silencieuse depuis une page `GET`.
- Les détails techniques bruts et payloads ne sont volontairement pas conservés,
  ce qui protège les secrets mais limite le diagnostic fournisseur avancé.

## 8. Proposition exacte pour la phase suivante

Exécuter la phase 7 sans modifier les contrats de connexion :

1. enrichir les vues immobilier, private equity et prêts avec synthèses valeur
   brute, capital restant, valeur nette, rendement et historique ;
2. lier clairement prêts, comptes et biens tout en vérifiant l'ownership ;
3. compléter les valorisations manuelles datées sans données opaques
   indispensables aux calculs ;
4. ajouter les échéances/remboursements nécessaires au suivi réel, sans encore
   mélanger le moteur de simulation de phase 8 ;
5. ajouter les snapshots spécialisés et graphiques ApexCharts ;
6. maintenir les calculs en `Decimal`, l'idempotence et les exports existants ;
7. couvrir les vues synthétiques/détaillées et l'isolation inter-utilisateur.

## 9. Questions nécessitant validation

Aucune décision ne bloque l'utilisation locale de la phase 6. Enable Banking
est activé comme adaptateur gratuit par défaut pour les propres comptes, sans
introduire Powens ou un autre fournisseur payant.

L'accès réel reste à initialiser par l'utilisateur dans Enable Banking et
Binance, sans jamais transmettre les clés ou mots de passe dans l'interface ou
le dépôt. Avant un enrichissement ultérieur, deux choix devront être validés :
le fournisseur de lecture d'adresses BTC/ETH pour Ledger, puis la priorité entre
l'historique Binance étendu et un second agrégateur bancaire.
