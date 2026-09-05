# Connecteurs financiers en lecture seule

## Choix open banking pour un usage personnel

FundBoard utilise `OpenBankingProvider`, une interface AIS (Account Information
Service) qui ne reçoit jamais les identifiants de la banque. Le fournisseur
actif est remplaçable sans modifier le modèle canonique, l'interface ou le
service d'idempotence.

Comparaison issue des documentations officielles consultées le 5 septembre
2026 :

| Fournisseur | Couverture et données annoncées | Consentement / intégration | Coût accessible publiquement | Décision FundBoard |
|---|---|---|---|---|
| [Enable Banking](https://enablebanking.com/docs/api/linked-accounts) | API comptes, soldes et transactions dans l'EEE ; [couverture France](https://enablebanking.com/open-banking-apis?country=FR) publiée banque par banque | OAuth/PSD2, sandbox et production ; durée réelle plafonnée par la banque, souvent jusqu'à 180 jours ; polling paginé | Les [conditions](https://enablebanking.com/terms/) rendent gratuit l'usage du Control Panel/API dans leur périmètre ; le mode restreint documenté limite une application personnelle à ses propres comptes | **Retenu par défaut** pour ce projet personnel |
| [Powens](https://docs.powens.com/documentation/integration-guides/bank/introduction-to-bank) | Plus de 1 800 institutions annoncées, comptes de paiement, soldes et au moins trois mois de transactions ; Wealth complète l'investissement | Webview, sandbox limitée à 50 connexions ; la [production exige un contrat](https://docs.powens.com/console-webview/console/introduction/set-up-your-powens-console-account) | Aucun tarif de production public trouvé, devis/contrat requis | Adaptateur futur si un contrat personnel devient possible |
| [GoCardless Bank Account Data](https://docs.gocardless.com/docs/bank-account-data) | Comptes, soldes, transactions et historique pouvant atteindre 24 mois selon la banque | Flux de réquisition PSD2 ; limites bancaires possibles, parfois quatre appels par jour et par compte | Aucun tarif actuel suffisamment clair sur la documentation publique consultée | Alternative future à revalider avant activation |
| [Bridge](https://docs.bridgeapi.io/reference/get-started) | Agrégation bancaire européenne, comptes et transactions | Sandbox gratuite ; passage en production accompagné | Production commerciale sur contact, sans grille publique trouvée | Alternative française future si le coût est accepté |

Le site de [Powens Wealth](https://www.powens.com/products/wealth/) cite bien
Finary comme client. Cela confirme la technologie utilisée par Finary, mais ne
rend pas l'offre Powens gratuite pour une application personnelle. Aucun
fournisseur payant n'est introduit par cette phase.

Les banques disponibles, la profondeur d'historique, la durée de consentement,
les webhooks, la résidence des données et les obligations contractuelles
restent propres au fournisseur et parfois à chaque banque. Elles doivent être
revérifiées avant tout passage à un usage public ou commercial.

## Activer Enable Banking

1. Créer un compte dans le Control Panel Enable Banking et une application de
   production en mode restreint, liée uniquement à ses propres comptes.
2. Générer la paire RSA selon le
   [quick start officiel](https://enablebanking.com/docs/api/quick-start/).
3. Conserver la clé privée hors du dépôt, avec des permissions système
   restrictives, puis configurer :

   ```dotenv
   FUNDBOARD_ENABLE_BANKING_APPLICATION_ID=identifiant-application
   FUNDBOARD_ENABLE_BANKING_PRIVATE_KEY_PATH=/chemin/prive/enable-banking.pem
   ```

4. Dans **FundBoard > Connexions**, créer la banque avec son nom ASPSP exact,
   cliquer sur **Autoriser ma banque**, terminer le consentement sur le site de
   la banque, puis **Tester la lecture** et **Synchroniser**.

Le callback vérifie un `state` aléatoire attaché à la session Django. La base
ne conserve que l'identifiant de session Enable Banking, l'IBAN masqué et une
référence opaque `env:enable_banking`. Elle ne reçoit jamais identifiant, mot de
passe, code PIN ou second facteur bancaire. La déconnexion demande la révocation
distante puis efface l'identifiant de session et la référence de secret, tout en
conservant l'historique financier local.

## Binance Spot

Créer une clé API Binance dédiée en désactivant **Enable Spot & Margin Trading**
et tout retrait. Placer ses valeurs uniquement dans l'environnement :

```dotenv
FUNDBOARD_BINANCE_API_KEY=identifiant-public
FUNDBOARD_BINANCE_SECRET_KEY=secret-prive
```

Le client ne possède que des appels HTTP `GET`. Il synchronise l'horloge,
signe avec HMAC-SHA256, impose `recvWindow=5000`, applique des timeouts, trois
tentatives avec backoff sur 429/5xx, puis refuse la clé si `canTrade` ou
`canWithdraw` est actif. Les soldes Spot deviennent des positions et les trades
des transactions idempotentes. Les paires sont paginées par `fromId` et le
curseur n'avance qu'après persistance.

Les stablecoins USDT, USDC et FDUSD sont présentés comme USD pour la
contre-valeur monétaire, tout en conservant l'actif de règlement exact dans les
métadonnées. Les dépôts/retraits on-chain, conversions et rewards ne sont pas
encore normalisés : les soldes restent justes, mais l'historique peut être
incomplet jusqu'à cet enrichissement.

## Ledger Live

Le connecteur Ledger est volontairement local et sans capacité de signature.
Il accepte un export CSV Ledger Live, cumule les quantités par compte et actif,
et crée une transaction seulement si une contre-valeur monétaire historique
valide est disponible. Quantité, prix de marché et coût d'acquisition restent
distincts ; aucune valeur actuelle n'est inventée.

FundBoard ne demande jamais de seed, phrase de récupération, passphrase ou clé
privée. Les adresses publiques et xpub ne sont pas encore interrogés : leur
ajout nécessitera un fournisseur blockchain explicite. Ils exposent l'historique
et les avoirs du portefeuille à toute personne qui les connaît, d'où leur
absence de la première interface tant que ce choix n'est pas validé.

## Trade Republic

Trade Republic documente officiellement le partage de son **compte courant**
avec un prestataire tiers réglementé AIS. FundBoard propose donc, dans
**Connexions**, le choix « Trade Republic — compte courant automatique
(PSD2) », implémenté par l'adaptateur Enable Banking. Le consentement est donné
sur le parcours bancaire, dure au maximum 180 jours et exige que le compte
courant Trade Republic soit activé. Cette connexion synchronise le solde espèces
et, lorsque les données le permettent, les opérations du compte ; elle ne donne
pas accès au CTO/PEA, aux positions titres ou aux ordres.

Sources officielles :

- [partage du compte courant Trade Republic avec un TPP](https://traderepublic.com/en-de/support?articleId=488f48ff-8cbc-4832-b1b4-21bcd72cc7b1) ;
- [marché allemand Enable Banking, où Trade Republic est listé](https://enablebanking.com/docs/markets/de/) ;
- [annonce de l'intégration Trade Republic par Enable Banking](https://enablebanking.com/blog/2026/12/08/enable-banking-changelog-july-2026).

L'intégration Enable Banking publiée pour Trade Republic passe actuellement par
l'ASPSP allemand (`country=DE`). Sa documentation indique que les opérations
n'exposent que montant, devise et date de comptabilisation. FundBoard exige en
plus un `entry_reference` ou `transaction_id` stable : sans lui, l'opération
est invalide, entièrement ignorée et comptée comme rejetée. Ce choix évite les
collisions entre deux mouvements de même montant le même jour. Le solde du
compte reste synchronisable même lorsqu'aucune opération ne peut être importée.

L'archive de scraper fournie a été analysée comme documentation technique, pas
copiée. Elle utilise téléphone, PIN, 2FA, cookie de session et WebSocket privé.
Les [conditions client officielles de Trade Republic](https://assets.traderepublic.com/assets/files/CA_SK-en.pdf)
interdisent les accès et interfaces non fournis par Trade Republic en dehors de
l'application. Ce flux n'est donc pas activé :
`FUND_BOARD_TRADE_REPUBLIC_LIVE_ENABLED=False` reste obligatoire. FundBoard ne
demande jamais le [PIN ou le code SMS](https://support.traderepublic.com/fr-fr/1686).

L'import JSON/CSV local reste disponible comme secours après acceptation de son
caractère expérimental. Il exige un identifiant stable, une date, un montant et
une devise ; toute ligne invalide est entièrement ignorée et journalisée. Pour
les titres, l'import manuel demeure la seule voie mise en œuvre tant que Trade
Republic ou un partenaire autorisé ne fournit pas une API patrimoniale adaptée
aux particuliers.

## Idempotence, erreurs et planification

Chaque exécution produit un `ConnectorSyncRun` avec déclencheur, état, curseur,
compteurs et identifiant de corrélation. Le journal ne contient ni payload brut,
ni clé, ni valeur de formulaire. Les comptes sont uniques par connexion et
identifiant externe, les instruments passent par `ExternalIdentifier` et les
transactions par une clé `{provider}:{external_id}`. Une seconde exécution ne
duplique rien.

Pour Binance, une déconnexion retire la référence locale mais ne peut pas
supprimer une clé avec une API elle-même limitée à la lecture : la clé doit
aussi être révoquée dans l'interface Binance. Pour Enable Banking, la session
AIS est supprimée à distance avant l'effacement de sa référence locale.

Une erreur d'accès conserve le dernier état financier valide. Une donnée
individuelle invalide est rejetée seule ; le run devient `PARTIAL`. Deux runs
concurrents sur la même connexion sont interdits en base.

La synchronisation reste manuelle par défaut. La phase 10 fournit une commande
unifiée pour cron ou systemd ; sans `--with-network`, elle reste entièrement
locale :

```bash
cd Mizzac
python3 manage.py run_fundboard_maintenance --with-network --fail-on-partial
python3 manage.py run_fundboard_maintenance --username mon_utilisateur --with-network
```

Avec l'option, la commande actualise d'abord le change EUR/USD et les seuls
instruments suivis, puis les connexions arrivées à `next_sync_at`. Un succès
programme la prochaine tentative selon `FUNDBOARD_SYNC_INTERVAL_MINUTES` ; un
échec utilise `FUNDBOARD_SYNC_RETRY_MINUTES`. Cette commande effectue de vrais
appels réseau. Les pages `GET`, les tests et les imports de fichiers n'en
effectuent aucun. Le guide complet et les unités systemd se trouvent dans
`OPERATIONS.md` et `deploy/systemd/`.

## Ajouter un autre fournisseur

Un adaptateur implémente `ConnectorProvider` ou `OpenBankingProvider`, valide sa
configuration non secrète et renvoie uniquement des DTO `RemoteAccount`,
`RemoteInstrument`, `RemotePosition`, `RemoteTransaction` et `SyncPayload`. Le
service commun prend en charge l'isolation par utilisateur, la validation du
modèle, l'idempotence, les compteurs, l'audit et l'interface. Un nouveau
fournisseur réseau doit fournir des tests mockés de pagination, retry,
permissions et révocation avant son ajout au registre.

La checklist détaillée d'ajout est disponible dans `ADDING_CONNECTOR.md`.
