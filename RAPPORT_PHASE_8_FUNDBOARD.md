# Rapport de phase 8 — Simulateurs

Date de validation : 5 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`  
Version unique : Python 3.12 / Django 6.1.1

## 1. Résumé du résultat fonctionnel

La phase 8 est terminée. FundBoard dispose d'une section **Simulations** dont
les scénarios sont privés, persistants et structurellement séparés du patrimoine
réel.

Le simulateur de prêt amortissable à taux fixe prend en charge :

- mensualité calculée depuis une durée ou durée calculée depuis une mensualité ;
- assurance mensuelle fixe ou taux annuel sur capital initial/restant ;
- frais initiaux ;
- différé partiel avec intérêts payés ou total avec intérêts capitalisés ;
- remboursement anticipé ponctuel et remboursement mensuel récurrent ;
- tableau d'amortissement complet, date de fin, intérêts, assurance, coût total
  et montant total versé.

Le simulateur d'intérêts composés prend en charge capital initial, versements
mensuels/trimestriels/semestriels/annuels, début ou fin de période, durée,
rendement nominal, frais, inflation et fiscalité finale simplifiée. Il produit
valeurs nominale/réelle, versements, gains, frais, impôt et série mensuelle.

Deux à quatre scénarios de même famille et de même devise peuvent être comparés
côte à côte et dans un graphique ApexCharts. Chaque scénario est exportable en
JSON et Excel.

## 2. Constats et décisions prises

- Les modèles ne stockent que les hypothèses. Les résultats sont recalculés par
  des services Python purs, indépendants de Django et sans appel réseau.
- Les scénarios n'ont aucune relation vers `Account`, `Loan`, `Position` ou
  `Transaction`. Leur création ne peut pas modifier le patrimoine réel.
- Les calculs utilisent exclusivement `Decimal`. Chaque opération mensuelle est
  arrondie à `0,01` avec `ROUND_HALF_UP` ; la dernière échéance absorbe le
  reliquat afin de terminer exactement à zéro.
- Les taux du moteur composé sont nominaux : rendement, frais et inflation sont
  divisés par douze. Cette convention est visible dans l'interface et la
  documentation.
- Le remboursement anticipé conserve la mensualité normale et réduit la durée.
  Les éventuelles indemnités contractuelles ne sont pas inventées.
- La fiscalité composée est explicitement simplifiée : taux unique appliqué à
  la fin sur le gain positif après frais.
- Les comparaisons multidevises sont refusées plutôt que d'appliquer un change
  implicite.
- Les noms ressemblant à des formules sont neutralisés dans Excel, et les
  séries de graphiques passent par `json_script`.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/services/loan_calculator.py` ;
- `Mizzac/FundBoard/services/compound_interest.py` ;
- `Mizzac/FundBoard/exports/simulations.py` ;
- `Mizzac/FundBoard/view_modules/simulations.py` ;
- `Mizzac/FundBoard/templates/fundboard/simulations.html` ;
- `loan_simulation_detail.html` et `loan_simulation_compare.html` ;
- `compound_simulation_detail.html` et `compound_simulation_compare.html` ;
- `Mizzac/FundBoard/tests/test_simulations.py` ;
- `Mizzac/FundBoard/SIMULATIONS_PHASE_8.md` ;
- `Mizzac/FundBoard/migrations/0006_compoundinterestscenario_loansimulationscenario.py` ;
- présent rapport.

Modifications principales :

- `Mizzac/FundBoard/models.py`, `forms.py`, `admin.py` et `urls.py` ;
- navigation secondaire FundBoard ;
- modèle canonique et `README.md`.

## 4. Migrations et impact sur les données

La migration `FundBoard.0006` crée :

- `LoanSimulationScenario`, avec hypothèses de financement, contraintes de
  montants et index utilisateur/archivage ;
- `CompoundInterestScenario`, avec hypothèses de placement, bornes de durée,
  frais, rendement et fiscalité, plus index utilisateur/archivage.

Les deux tables sont nouvelles et n'altèrent aucune donnée financière existante.
La migration a été appliquée avec succès sur la base vierge
`/tmp/mizzac-phase8-fresh.sqlite3`. La base du dépôt n'a pas été modifiée.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `make ci` sous Django 6.1.1 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `pytest --cov --cov-report=term-missing` | 149 tests réussis ; couverture 82,46 % |
| `python3 -Wd -m pytest -q` | 149 tests et 89 sous-tests réussis, sans avertissement |
| `manage.py migrate --noinput` sur SQLite vierge | toutes les migrations appliquées, dont `FundBoard.0006` |
| `manage.py check --deploy` avec HTTPS/HSTS | aucun problème |
| `node --check` sur `charts.js` et `currency.js` | syntaxe valide |
| version Django importée | `6.1.1` |
| `git diff --check` | aucune erreur d'espace ou marqueur de conflit |

Les 21 tests spécifiques couvrent taux fixe et taux nul, deux modes de calcul,
différés, assurance fixe/proportionnelle, remboursements ponctuels/récurrents,
dates de fin de mois, fréquence des versements, frais, inflation, fiscalité,
comparaison, exports, injection JSON/Excel, archivage et isolation utilisateur.

## 6. Description des écrans concernés

- **Simulations** : avertissement sur la nature hypothétique, deux tableaux de
  scénarios, résultats résumés, sélection de deux à quatre éléments et boutons
  de création.
- **Détail prêt** : mensualité, durée, intérêts, coût, hypothèses, courbe du
  capital restant et tableau mensuel complet.
- **Comparaison de prêts** : cartes de mensualité/durée/coût et courbes du
  capital restant.
- **Détail intérêts composés** : valeur nominale/réelle, total versé, gains,
  coûts, hypothèses, courbe et calendrier mensuel.
- **Comparaison composée** : résultats côte à côte et courbes nominales.
- Les détails offrent modification, archivage conservatif et téléchargements
  JSON/Excel.

Aucune capture automatisée n'a été produite. Le rendu des templates, les routes
et les permissions ont été validés avec le client Django.

## 7. Risques, limites et dette technique restante

- Les résultats ne sont ni contractuels ni garantis et ne constituent pas un
  conseil financier.
- Le prêt est limité au taux fixe amortissable. Taux variable, prêt in fine,
  garantie, pénalités, modulation et conventions bancaires spécifiques ne sont
  pas encore modélisés.
- Le rendement composé est constant : il ne simule ni volatilité, ni séquence
  de rendements, ni risque de perte variable.
- La fiscalité est volontairement générique et ne représente aucune enveloppe
  ou législation précise.
- Une durée maximale de 100 ans peut produire 1 200 lignes dans un détail ou un
  export. Ce volume reste acceptable pour l'usage personnel, mais une
  pagination/agrégation annuelle serait utile en cas de nombreux scénarios.
- Les scénarios sont recalculés à chaque affichage et ne portent pas encore de
  version immuable des résultats. L'export contient toutefois toutes les
  hypothèses et la règle d'arrondi nécessaires à la reproduction.

## 8. Proposition exacte pour la phase suivante

Exécuter la phase 9 en maintenant une séparation absolue avec les comptes réels :

1. créer portefeuille, cash, positions, watchlist et ordres exclusivement
   virtuels ;
2. implémenter les ordres `MARKET` et `LIMIT`, entiers ou fractionnaires selon
   l'instrument ;
3. appliquer frais, spread et slippage configurables ;
4. exécuter uniquement depuis un cours horodaté déjà disponible, sans donnée
   future, et signaler tout cours différé ;
5. suivre PRU, gains réalisés/non réalisés, dividendes, splits et performance ;
6. ajouter benchmark, journal, annulation des ordres ouverts, clonage, remise à
   zéro et export ;
7. afficher partout un badge « portefeuille virtuel » et tester l'absence de
   tout chemin vers un ordre réel.

## 9. Questions nécessitant validation

Aucune décision ne bloque l'utilisation locale de la phase 8.

Les conventions les plus structurantes — taux nominaux divisés par douze,
remboursement anticipé réduisant la durée et fiscalité finale générique — sont
documentées et modifiables ultérieurement si un produit bancaire ou une
enveloppe fiscale précise doit être reproduit.
