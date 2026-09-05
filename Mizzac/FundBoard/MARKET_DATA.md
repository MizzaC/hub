# Données de marché et valorisation

## Choix des fournisseurs

FundBoard utilise trois adaptateurs remplaçables, exclusivement en lecture :

| Donnée | Adaptateur par défaut | Identifiant | Usage dans FundBoard |
|---|---|---|---|
| Actions, ETF, fonds et indices | Yahoo via `yfinance==1.7.0` | ticker Yahoo, par exemple `AIR.PA` | dernier cours, historique OHLCV, état et fuseau du marché |
| Cryptomonnaies | CoinGecko | identifiant CoinGecko, par exemple `bitcoin` | dernier cours et historique en USD |
| EUR/USD | Frankfurter v2, filtré sur `ECB` | paire ISO | taux de référence daté et taux inverse calculé |

Frankfurter ne demande pas de clé et agrège des sources publiques. L'adaptateur
demande explicitement `providers=ECB` afin de ne conserver que les taux de
référence publiés par la Banque centrale européenne. Ces taux sont indicatifs,
datés et non destinés à l'exécution d'ordres.

Yahoo via `yfinance` est réservé ici à l'usage personnel prévu par le projet.
Même si un état de marché est disponible, FundBoard marque systématiquement ces
cours « différés / non garantis » et ne les présente jamais comme temps réel.

CoinGecko est configurable avec une clé Demo. L'attribution CoinGecko est
affichée sur le détail d'une cryptomonnaie. Sans clé, l'accès public peut être
plus limité ; une panne ou un quota atteint ne supprime jamais le cache local.

Références officielles :

- [API Frankfurter v2](https://frankfurter.dev/) ;
- [API de données de la BCE](https://data.ecb.europa.eu/help/api/data) et
  [taux de référence de l'euro](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) ;
- [documentation `yfinance`](https://ranaroussi.github.io/yfinance/) ;
- [documentation de l'API CoinGecko](https://docs.coingecko.com/).

## Configuration

Les valeurs par défaut sont présentes dans `.env.example` :

```dotenv
FUND_BOARD_EQUITY_PROVIDER=yahoo
FUND_BOARD_CRYPTO_PROVIDER=coingecko
COINGECKO_API_KEY=
```

Une crypto doit porter son identifiant CoinGecko dans le formulaire de
l'instrument. Le ticker seul (`BTC`) n'est jamais utilisé comme identifiant
CoinGecko implicite : il faut renseigner l'identifiant exact, tel que `bitcoin`.

Dans **Marché et devises**, les valeurs initiales sont :

- patrimoine consolidé : EUR ;
- actions, ETF, fonds et indices : EUR ;
- cryptomonnaies : USD ;
- benchmark : `^STOXX50E`.

Les boutons **Défaut / EUR / USD** changent immédiatement l'affichage des
positions lorsque le taux EUR/USD est présent. Ils ne modifient aucune donnée,
n'effectuent aucun appel réseau et retombent sur la devise d'origine si la
conversion est impossible.

## Collecte, cache et erreurs

Les pages `GET` lisent uniquement la base locale. Un appel réseau est possible
uniquement après une action `POST` authentifiée et protégée par CSRF :

1. **Actualiser EUR/USD** enregistre le taux direct Frankfurter/ECB et son
   inverse dans une transaction atomique ;
2. **Actualiser le cours** récupère le dernier cours et jusqu'à 365 jours
   d'historique, puis met à jour les positions détenues ;
3. **Actualiser le benchmark** crée si nécessaire un instrument système privé
   et remplit son historique.

Les écritures sont idempotentes par instrument, source et horodatage. En cas
d'erreur, le statut de collecte passe en erreur mais le dernier cours ou taux
valide reste disponible. Aucun message technique fournisseur n'est rendu dans
l'interface utilisateur.

La fraîcheur effective est recalculée à la lecture : deux heures pour une
cryptomonnaie, quatre jours pour les autres instruments et quatre jours pour le
change (ce qui couvre un week-end normal). L'écran détail affiche toujours la
source, la devise, l'instant observé, le fuseau et l'état de marché disponible.

## Valorisation, snapshots et reproductibilité

Les services financiers utilisent uniquement `Decimal` et les valeurs en cache.
Une valeur inter-devise n'entre dans le total qu'avec un taux, sa date et sa
source. Une ligne non valorisable est exclue et signalée : les devises ne sont
jamais additionnées directement.

Le bouton **Créer le snapshot du jour** et la commande suivante figent les
valeurs source, valeurs converties, taux, dates et sources :

```bash
cd Mizzac
python3 manage.py create_portfolio_snapshots
python3 manage.py create_portfolio_snapshots --username mon_utilisateur
```

La commande ne contacte aucun fournisseur. Elle est rejouable le même jour et
refuse entièrement un utilisateur dont la valorisation est incomplète. Elle
peut être planifiée quotidiennement par cron ou systemd après les
actualisations explicites ; la planification automatisée des connecteurs reste
du ressort de la phase 6/10.

Le dashboard calcule sa performance Modified Dietz depuis deux journées de
snapshots et les flux externes datés. Le benchmark utilise son historique local.

## Limites assumées

- Il n'existe pas de garantie temps réel ni de SLA fournisseur.
- Le cours quotidien Yahoo ne représente pas un prix d'exécution.
- Le taux BCE est un taux de référence, pas nécessairement le taux facturé par
  une banque ou une plateforme.
- La conversion rapide est actuellement limitée à EUR/USD.
- Les opérations sur titres Yahoo sont exposées par l'adaptateur mais ne sont
  pas encore appliquées automatiquement aux transactions ou positions.
- Les tests n'accèdent jamais au réseau : les contrats fournisseurs y sont
  simulés.
