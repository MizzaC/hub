# Rapport de phase 7 — Immobilier, private equity et prêts

Date de validation : 5 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`  
Version unique : Python 3.12 / Django 6.1.1

## 1. Résumé du résultat fonctionnel

La phase 7 est terminée. FundBoard propose désormais des vues synthétiques et
détaillées pour les biens immobiliers, les prêts et les participations de
private equity. Chaque détail associe les valeurs courantes, leurs dates et
leurs sources à un historique ApexCharts alimenté depuis la base locale.

Les indicateurs suivants sont calculés exclusivement en `Decimal` :

- immobilier : valeur détenue brute et nette, dette liée, plus-value latente,
  loyers, vacance, coûts, revenu annuel et rendements brut/net ;
- prêts : capital remboursé/restant, progression, échéance et assurance
  annualisées, biens liés ;
- private equity : engagement appelé/non appelé, NAV, distributions, gain,
  DPI, RVPI et TVPI.

En complément de la phase demandée, FundBoard offre une voie sans fichier pour
le **compte espèces** Trade Republic : un consentement PSD2 via Enable Banking.
Cette voie ne couvre pas les positions CTO/PEA. Le scraper privé fourni n'est
pas intégré.

## 2. Constats et décisions prises

- Les valorisations spécialisées sont manuelles, datées, sourcées et
  idempotentes par objet/date/source. Une observation historique n'écrase pas
  une valeur courante plus récente.
- Un prêt peut être rattaché à un compte et à un ou plusieurs biens, avec
  vérification de propriété par l'utilisateur.
- Une dette n'est soustraite d'un bien que si les deux devises correspondent.
  Sinon la valeur nette reste indéterminée et l'interface avertit que le total
  est incomplet.
- Les multiples private equity ont pour dénominateur le capital appelé. Ils ne
  sont pas inventés lorsque celui-ci est nul ; le capital appelé ne peut pas
  excéder l'engagement.
- Le simulateur de prêt, les échéanciers théoriques et les projections restent
  en phase 8 afin de ne pas confondre observation réelle et simulation.
- Trade Republic autorise officiellement le partage du compte courant avec un
  prestataire AIS réglementé. Enable Banking liste Trade Republic comme ASPSP
  allemand ; le formulaire spécialisé crée donc une connexion Enable Banking
  `DE`, personnelle, avec un consentement maximal de 180 jours.
- La documentation Enable Banking indique actuellement seulement montant,
  devise et date pour les mouvements Trade Republic. FundBoard rejette toute
  opération dépourvue d'identifiant stable, conformément à la règle demandée
  « ligne invalide non importée ». Le solde peut néanmoins être synchronisé.
- Les conditions client Trade Republic interdisent les accès/interfaces non
  fournis en dehors de l'application. L'authentification téléphone/PIN/2FA et
  le WebSocket privé du scraper ne sont donc pas repris.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/services/assets.py` : métriques spécialisées et agrégats
  séparés par devise ;
- `Mizzac/FundBoard/services/asset_history.py` : écritures atomiques des trois
  historiques ;
- `Mizzac/FundBoard/view_modules/assets.py` : vues de détail, private equity et
  modales de valorisation ;
- `Mizzac/FundBoard/templates/fundboard/real_estate_detail.html` ;
- `Mizzac/FundBoard/templates/fundboard/loan_detail.html` ;
- `Mizzac/FundBoard/templates/fundboard/private_equity.html` et
  `private_equity_detail.html` ;
- `Mizzac/FundBoard/tests/test_assets.py` ;
- `Mizzac/FundBoard/ASSETS_PHASE_7.md` ;
- `Mizzac/FundBoard/migrations/0005_loanbalancesnapshot_privateequityvaluation_and_more.py` ;
- présent rapport.

Modifications principales :

- `Mizzac/FundBoard/models.py`, `forms.py`, `admin.py` et `urls.py` ;
- vues/listes immobilier et prêts, navigation FundBoard et exports/imports
  rétrocompatibles ;
- adaptateur Enable Banking, formulaire et écrans de connexion pour le compte
  espèces Trade Republic ;
- tests connecteurs, modèle canonique, documentation connecteurs et `README.md`.

## 4. Migrations et impact sur les données

La migration `FundBoard.0005` :

- ajoute la date du capital restant dû à `Loan` ;
- crée `LoanBalanceSnapshot` et `PrivateEquityValuation` avec unicité
  objet/date/source et contraintes de montants positifs ;
- ajoute assurance annuelle, autres coûts et vacance à `RealEstate` ;
- ajoute la source de valorisation à `PrivateEquityHolding` et contraint le
  capital appelé à rester inférieur ou égal à l'engagement ;
- initialise un historique à partir des valeurs courantes éventuellement déjà
  présentes, avec la source réversible `phase7-initial`.

La migration a été appliquée avec succès sur la base vierge
`/tmp/mizzac-phase7-fresh.sqlite3`. La base du dépôt n'a pas été modifiée. Comme
confirmé, le projet peut repartir de zéro ; si une ancienne base non prévue
contenait un capital appelé supérieur à l'engagement, il faudrait corriger cette
ligne avant migration plutôt que la transformer silencieusement.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `make ci` sous Django 6.1.1 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `pytest --cov --cov-report=term-missing` | 128 tests réussis ; couverture 81,31 % |
| `python3 -Wd -m pytest -q` | 128 tests et 89 sous-tests réussis, sans avertissement |
| `manage.py migrate --noinput` sur SQLite vierge | toutes les migrations appliquées, dont `FundBoard.0005` |
| `manage.py check --deploy` avec HTTPS/HSTS | aucun problème |
| `node --check` sur `charts.js` et `currency.js` | syntaxe valide |
| version Django importée | `6.1.1` |
| `git diff --check` | aucune erreur d'espace ou marqueur de conflit |

Les tests de phase couvrent les formules exactes, les contraintes, la mise à
jour chronologique, l'isolation entre utilisateurs, les routes privées, le JSON
de graphiques sûr, la création du connecteur Trade Republic PSD2 et le rejet
d'une opération sans identifiant stable.

## 6. Description des écrans concernés

- **Immobilier** : cartes par bien, totaux par devise, dette et valeur nette,
  rendements, fraîcheur et avertissement en cas de dette dans une autre devise.
- **Détail immobilier** : quatre indicateurs, détail annuel des revenus/coûts,
  prêt lié et courbe des valorisations.
- **Prêts** : synthèse des passifs, capital et date d'observation.
- **Détail prêt** : progression, taux, échéance, assurance, biens liés et courbe
  du capital restant dû.
- **Private equity** : engagements et valorisations agrégés par devise, cartes
  individuelles et TVPI.
- **Détail private equity** : engagement, NAV, distributions, DPI/RVPI/TVPI et
  graphe comparatif de l'historique.
- **Connexions** : nouveau choix « Trade Republic — compte courant automatique
  (PSD2) » et avertissement clair sur la portée espèces uniquement.

Aucune capture automatisée n'a été produite. Les templates, permissions,
routes et contenus ont été validés avec le client Django.

## 7. Risques, limites et dette technique restante

- Les valorisations immobilières et private equity restent déclaratives ;
  FundBoard ne les présente pas comme une expertise ou un relevé officiel.
- Les rendements immobiliers sont indicatifs : ils n'intègrent que les champs
  saisis et pas fiscalité personnelle, inflation ou coût d'opportunité.
- Aucun taux implicite n'est utilisé pour soustraire une dette dans une autre
  devise. Une conversion datée pourra enrichir ce cas ultérieurement.
- Le modèle suit le capital restant dû observé, mais pas encore les échéances
  réelles détaillées en principal/intérêts.
- Trade Republic PSD2 dépend de la disponibilité de l'ASPSP allemand pour le
  compte de l'utilisateur et nécessite un vrai consentement Enable Banking.
  Aucun compte réel n'a été contacté pendant les tests.
- Cette API ne donne pas les titres. Les mouvements sans identifiant stable
  sont rejetés, ce qui peut limiter l'historique automatique au solde courant.
- La disponibilité et les conditions d'Enable Banking peuvent évoluer ; elles
  devront être revalidées avant un usage autre que strictement personnel.

Références officielles : [partage TPP Trade Republic](https://traderepublic.com/en-de/support?articleId=488f48ff-8cbc-4832-b1b4-21bcd72cc7b1),
[couverture allemande Enable Banking](https://enablebanking.com/docs/markets/de/),
[conditions client Trade Republic](https://assets.traderepublic.com/assets/files/CA_SK-en.pdf)
et [sécurité PIN/SMS](https://support.traderepublic.com/fr-fr/1686).

## 8. Proposition exacte pour la phase suivante

Exécuter la phase 8 sans modifier les observations réelles de phase 7 :

1. créer des scénarios privés distincts des prêts et actifs réels ;
2. implémenter un prêt amortissable en `Decimal`, avec mensualité, principal,
   intérêts, assurance et tableau d'amortissement ;
3. ajouter un simulateur d'intérêts composés avec versements périodiques ;
4. comparer plusieurs scénarios avec hypothèses et résultats visibles ;
5. afficher les courbes avec l'intégration ApexCharts commune ;
6. permettre l'export des scénarios et résultats ;
7. tester cas limites, arrondis, ownership et absence d'effet sur le patrimoine
   réel.

## 9. Questions nécessitant validation

Aucune décision ne bloque l'usage local de la phase 7.

Pour Trade Republic, la meilleure automatisation conforme trouvée est activée
pour le compte espèces via Enable Banking. Il n'existe pas, parmi les interfaces
officielles identifiées, de voie équivalente pour synchroniser les positions
titres d'un particulier. L'import local reste donc le secours pour le CTO/PEA ;
le scraper privé demeure volontairement désactivé.
