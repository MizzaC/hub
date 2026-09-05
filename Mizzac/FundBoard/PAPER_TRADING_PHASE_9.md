# Portefeuilles virtuels — phase 9

## Séparation avec le patrimoine réel

Le paper trading utilise son propre registre : `VirtualPortfolio`,
`VirtualWatchlistEntry`, `VirtualPosition`, `VirtualOrder`, `VirtualCashEvent`,
`VirtualCorporateAction` et `VirtualPortfolioSnapshot`. Aucun de ces modèles ne
référence `Account`, la `Position` réelle, `Transaction` ou `Connection`.

Le moteur n'importe aucun connecteur et ne réalise aucun appel HTTP. Il lit
uniquement les lignes `Price` déjà enregistrées. Il n'existe donc aucun chemin
de ce module vers un ordre de courtier, une banque ou une plateforme crypto.
Les écrans et chaque ligne d'ordre portent un marquage « virtuel » explicite.

## Portefeuille, watchlist et quantités

Un portefeuille définit une devise de base, un capital initial strictement
positif, son cash fictif et, en option, un benchmark. Le capital et la devise
initiale deviennent immuables dans le formulaire après création ; les frais,
le spread, le slippage et le benchmark restent modifiables.

Un instrument partagé ou appartenant à l'utilisateur doit être ajouté à la
watchlist avant tout ordre. Les quantités fractionnaires sont autorisées par
défaut pour les cryptomonnaies et désactivées par défaut pour les autres
instruments. Ce réglage est conservé par entrée de watchlist.

Les indices, devises et participations non cotées ne sont pas négociables dans
ce moteur. Les ventes à découvert, le levier et le cash négatif sont refusés.

## Règles d'exécution

Deux types d'ordre sont pris en charge :

- `MARKET`, exécuté dès qu'un cours local admissible existe ;
- `LIMIT`, exécuté si le prix simulé est inférieur ou égal à la limite pour un
  achat, ou supérieur ou égal à la limite pour une vente.

Le moteur sélectionne le dernier `Price` positif, non marqué en erreur, dont
`observed_at` est inférieur ou égal à l'instant d'exécution. Un cours futur ne
peut ainsi jamais être utilisé. La devise du cours doit être identique à celle
du portefeuille : aucune conversion implicite n'est appliquée à une exécution.

La politique de marché volontairement simple est la suivante :

- actions, ETF, fonds, obligations, matières premières et autres titres : cours
  de moins de 20 minutes et état `REGULAR` ;
- cryptomonnaies : marché 24/7 et cours de moins de 5 minutes.

Un ordre sans cours, hors séance, trop ancien ou dont la limite n'est pas
atteinte reste ouvert. Il peut être retraité après l'enregistrement d'un nouveau
cours, ou annulé. Une devise incompatible, un cash insuffisant ou une position
insuffisante provoque un rejet explicite.

Pour un cours local `P`, le prix unitaire simulé est :

```text
impact = spread / 2 + slippage
achat = P × (1 + impact / 10 000)
vente = P × (1 - impact / 10 000)
frais = frais fixes + montant brut × taux proportionnel / 100
```

Les montants de cash et frais sont arrondis au centime avec `ROUND_HALF_UP`.
Les prix gardent 12 décimales et les quantités 18 décimales. Le PRU d'achat
inclut les frais. Une vente comptabilise le résultat réalisé net de frais.
Chaque exécution fige le cours, son horodatage, sa source, son état de marché et
son éventuel caractère différé dans l'ordre : une actualisation ultérieure des
cours ne réécrit pas le journal.

## Performance et événements

La valorisation expose cash, positions, valeur totale, performance absolue et
relative au capital initial, gains réalisés, gains latents et dividendes. Les
résultats réalisés d'une position entièrement vendue restent inclus. Un cours
manquant rend la valorisation explicitement incomplète ; un cours différé est
signalé.

Les snapshots enregistrent ces valeurs et la valeur théorique du benchmark,
normalisée au capital initial depuis le dernier cours disponible à la création
du portefeuille. Le graphique ApexCharts central compare les deux séries.

Les dividendes et splits sont des événements manuels du registre virtuel. Un
dividende crédite le cash selon la quantité détenue lors de son application. Un
split ajuste quantité, PRU et ordres ouverts. Un événement futur reste en
attente et une seconde application est sans effet.

## Clonage, remise à zéro et exports

Le clonage crée un nouveau portefeuille indépendant depuis la valeur courante.
Il copie la watchlist et les positions actives, réinitialise leur référence de
performance au cours actuel et ne copie pas le journal d'ordres. La remise à
zéro supprime le journal simulé, les positions, événements et snapshots, remet
le cash au capital initial et conserve la watchlist. Elle nécessite une
confirmation explicite.

Les exports JSON 1.0 et Excel contiennent paramètres, valorisation, watchlist,
positions, ordres, cash, événements et snapshots. Les cellules pouvant être
interprétées comme des formules Excel sont neutralisées. Les exports sont
toujours filtrés par propriétaire.

## Limites

- Les ordres ouverts ne sont retraités automatiquement qu'à la demande ; leur
  planification appartient à la phase 10.
- Les horaires ne modélisent ni calendrier de jours fériés, ni enchères, ni
  interruptions de cotation. Ils reposent sur l'état du cours fourni.
- Les dividendes et splits sont saisis manuellement. La quantité utilisée est
  celle détenue au moment de l'application, pas une reconstruction historique à
  la date d'effet.
- Il n'y a ni carnet d'ordres, ni liquidité, ni exécution partielle, ni vente à
  découvert, ni marge, ni fiscalité.
- Une exécution multidevise est refusée. L'affichage EUR/USD commun reste
  disponible ailleurs, mais ne modifie jamais le registre d'exécution.

