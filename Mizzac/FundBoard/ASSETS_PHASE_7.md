# Immobilier, prêts et private equity — phase 7

## Saisie et historique

Les trois familles d'actifs sont privées et filtrées par utilisateur. Toute
création, modification, valorisation ou mise à jour du capital restant dû passe
par un formulaire authentifié, une requête `POST` protégée par CSRF et un
événement d'audit.

- Un bien conserve sa valeur estimée, sa date et sa source. Chaque observation
  est aussi enregistrée dans `RealEstateValuation`.
- Un prêt conserve son capital restant dû et sa date d'observation. Chaque
  observation est enregistrée dans `LoanBalanceSnapshot`.
- Une participation conserve ensemble valeur liquidative, capital appelé,
  distributions, date et source. Chaque observation est enregistrée dans
  `PrivateEquityValuation`.

Une observation plus ancienne enrichit l'historique sans remplacer la valeur
courante. Une observation à la même date et de même source est mise à jour au
lieu d'être dupliquée. Les graphiques sont rendus par l'intégration ApexCharts
commune à toutes les applications ; les données sont injectées par
`json_script`, sans code JavaScript construit depuis du texte utilisateur.

## Formules immobilières

Toutes les sommes sont pondérées par la quote-part de propriété :

```text
valeur brute = valeur estimée × quote-part
coût d'acquisition = (prix + frais + travaux) × quote-part
plus-value latente = valeur brute − coût d'acquisition
loyer brut annuel = loyer mensuel × 12 × quote-part
perte de vacance = loyer brut annuel × taux de vacance
charges annuelles = (charges mensuelles × 12 + taxe foncière
                     + assurance + autres coûts) × quote-part
revenu net annuel = loyer brut − vacance − charges annuelles
rendement brut = loyer brut annuel / coût d'acquisition
rendement net = revenu net annuel / coût d'acquisition
valeur nette = valeur brute − capital restant dû lié
```

Le prêt n'est soustrait que s'il utilise la devise du bien. Sinon FundBoard
affiche « conversion requise » et exclut la dette et la valeur nette concernées
des totaux. Aucune parité implicite n'est appliquée.

## Indicateurs des prêts

```text
capital remboursé = capital initial − capital restant dû
progression = capital remboursé / capital initial
mensualités annuelles = mensualité × 12
assurance annuelle = assurance mensuelle × 12
```

Ces indicateurs décrivent les valeurs saisies. Le tableau d'amortissement et le
calcul théorique des intérêts relèvent de la phase 8.

## Indicateurs private equity

Les montants suivants sont pondérés par la quote-part : engagement, capital
appelé, distributions et valeur liquidative (`NAV`).

```text
engagement non appelé = engagement − capital appelé
DPI = distributions / capital appelé
RVPI = NAV / capital appelé
TVPI = (distributions + NAV) / capital appelé
gain = distributions + NAV − capital appelé
```

Les multiples ne sont pas affichés lorsque le capital appelé est nul. La base
et les formulaires refusent un capital appelé supérieur à l'engagement, ainsi
que toute valeur historique négative.

## Devises, précision et limites

Les calculs utilisent exclusivement `Decimal`. Les agrégats restent séparés par
devise ; aucun total EUR/USD n'est produit sans taux daté. Les valorisations
sont manuelles et ne prétendent pas remplacer une expertise immobilière, un
relevé bancaire ou le rapport officiel d'un fonds. La phase 7 n'introduit ni
projection, ni hypothèse d'inflation, ni échéancier simulé.
