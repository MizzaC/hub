# Simulations financières — phase 8

## Séparation avec le patrimoine réel

`LoanSimulationScenario` et `CompoundInterestScenario` appartiennent directement
à un utilisateur. Ils n'ont aucune clé étrangère vers `Account`, `Loan`,
`Position` ou `Transaction`. Créer, modifier, comparer ou archiver un scénario
ne peut donc modifier ni une position, ni un solde, ni une valorisation réelle.

Les modèles conservent seulement les hypothèses. Les résultats et séries sont
recalculés à la demande par deux services Python purs, indépendants de Django :

- `services/loan_calculator.py` ;
- `services/compound_interest.py`.

Tous les calculs utilisent `Decimal`. Chaque mouvement mensuel est arrondi à
`0,01` avec `ROUND_HALF_UP`. La dernière échéance d'un prêt absorbe le reliquat
d'arrondi afin que le capital final soit exactement nul.

## Prêt amortissable à taux fixe

Le scénario peut soit calculer la mensualité depuis une durée totale, soit
calculer la durée depuis une mensualité cible. Le taux mensuel est le taux
nominal annuel divisé par douze.

Pour une durée donnée et un taux mensuel non nul :

```text
mensualité = capital × taux × (1 + taux)^nombre_de_mois
             / ((1 + taux)^nombre_de_mois − 1)
```

À taux nul, la mensualité est le capital divisé par le nombre de mois. Une
mensualité cible qui ne couvre pas les intérêts du premier mois est refusée. La
durée calculée est limitée à 1 200 mois.

Deux différés sont disponibles :

- **partiel** : le capital ne diminue pas et les intérêts mensuels sont payés ;
- **total** : aucun remboursement de prêt n'est versé et les intérêts mensuels
  sont ajoutés au capital.

L'assurance peut être un montant mensuel fixe ou un taux annuel appliqué au
capital initial ou au capital restant dû. Les frais initiaux sont intégrés au
coût total mais pas financés. Un remboursement anticipé peut être ponctuel ou
mensuel à partir d'un mois donné. La mensualité normale est alors conservée et
la durée diminue ; les éventuelles indemnités de remboursement anticipé ne sont
pas calculées.

Le tableau exporté contient pour chaque mois date, capital initial, échéance,
principal, intérêts, assurance, remboursement anticipé, versement total et
capital final.

## Intérêts composés

La projection fonctionne par mois. Le rendement et les frais saisis sont des
taux nominaux annuels divisés par douze. Les versements peuvent être mensuels,
trimestriels, semestriels ou annuels, au début ou à la fin de leur période.

Ordre des opérations mensuelles :

1. versement de début de période, le cas échéant ;
2. application et arrondi du rendement ;
3. prélèvement et arrondi des frais sur l'encours après rendement ;
4. versement de fin de période, le cas échéant.

La valeur réelle est la valeur nominale déflatée chaque mois par le taux
d'inflation nominal annuel divisé par douze. La fiscalité optionnelle est une
hypothèse volontairement simple : à la dernière période, un taux unique est
appliqué uniquement au gain positif restant après les frais. Elle ne modélise
ni enveloppe fiscale, ni abattement, ni report de moins-value, ni prélèvement en
cours de vie.

La série mensuelle expose versement, rendement, frais, fiscalité, valeur
nominale et valeur réelle. Les résultats résument valeur finale brute et nette,
total versé, gains, frais et impôt estimés.

## Comparaison et exports

La page **Simulations** compare de deux à quatre scénarios de même famille et de
même devise. Aucun taux de change implicite n'est utilisé. Les graphiques sont
rendus par l'intégration ApexCharts centrale et leurs données passent par
`json_script`.

Chaque scénario est exportable en :

- JSON versionné `1.0`, avec hypothèses, résumé, série complète et convention
  d'arrondi ;
- Excel, avec onglets `Hypothèses`, `Résultats` et `Amortissement` ou
  `Projection`.

Les cellules textuelles commençant comme une formule sont neutralisées. Les
exports et vues sont filtrés par utilisateur.

## Limites

Les résultats sont des projections non contractuelles et non garanties. La
première version ne couvre que les prêts amortissables à taux fixe. Elle
n'intègre pas taux variable, prêt in fine, frais de garantie, modulation
d'échéance, pénalités, fiscalité immobilière ou convention bancaire spécifique.

Le rendement des intérêts composés est constant et ne représente ni volatilité,
ni séquence de rendements, ni risque de perte. Les taux nominaux mensuels sont
un choix explicite ; ils ne doivent pas être confondus avec des taux annuels
effectifs.
