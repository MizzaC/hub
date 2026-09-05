# Rapport de phase 3 — Modèle financier canonique et services

> Note de version : les mentions de Django 5.2 ci-dessous décrivent des tests
> historiques. La seule version active du projet est désormais Django 6.1.1.

Date de validation : 4 septembre 2026  
Branche de travail : `mizeos-FundBoard-test`

## 1. Résumé du résultat fonctionnel

La phase 3 est terminée. FundBoard repose désormais sur un modèle financier
canonique indépendant des banques et fournisseurs : institutions, connexions,
comptes contenants, instruments, positions, transactions enrichies, cours,
taux de change, snapshots et identifiants externes.

Les quantités fractionnées, prix, taux et valeurs disposent d'une précision
adaptée aux titres et cryptoactifs. La devise d'origine, la valeur convertie,
le taux et sa date sont conservés ensemble. Les opérations importées ou
synchronisées ont une clé d'idempotence et les transferts internes peuvent
relier leurs deux jambes.

Les services Python purs calculent maintenant la valorisation d'une position,
les conversions, les quotes-parts, actifs, passifs, patrimoine net et
performance Modified Dietz. Les flux externes, revenus, frais, taxes, effet de
change et performance de marché restent distincts.

L'interface existante a été adaptée au nouveau schéma : comptes, positions,
transactions, qualité des connexions et modales continuent de fonctionner sans
changement de route.

## 2. Constats et décisions prises

- La confirmation qu'aucune base réelle n'existe vaut validation du
  remplacement direct proposé à la fin de la phase 2.
- Les cinq anciennes migrations FundBoard, dont la migration destructive
  `0005`, ont été remplacées par un seul `0001_initial` cohérent. Aucune façade
  de compatibilité de données n'est maintenue.
- Un compte est toujours un contenant ; un instrument est toujours un actif
  détenu. Un PEA ou un CTO reste donc un type de compte, jamais un type
  d'instrument.
- Les propriétaires privés sont explicites. Les relations compte/connexion,
  transaction/compte, snapshot/cible et identifiant/cible sont validées contre
  les croisements entre utilisateurs.
- Une première copropriété est couverte par `ownership_share`. Un modèle
  multi-propriétaire plus complexe est différé jusqu'à l'existence d'un cas
  réel.
- Les champs extensibles utilisent exclusivement `models.JSONField`. Aucun
  paquet `jsonfield` ni schéma propre à un fournisseur n'a été ajouté.
- Les secrets sont hors modèle. `Connection.secret_reference` ne peut contenir
  qu'une référence opaque vers un stockage externe.
- Un rejeu strictement identique retourne l'opération existante. La réutilisation
  d'une clé d'idempotence avec un autre contenu échoue explicitement.
- Les frais et taxes sont stockés positivement dans leurs champs détaillés,
  tandis que `net_amount` porte leur effet signé sur la trésorerie.
- Une jambe de transfert non appariée est traitée comme flux externe par
  prudence ; deux jambes appariées sont exclues de l'épargne et de la
  performance du portefeuille.
- Les calculs refusent les `float` binaires et travaillent en `Decimal` avec un
  arrondi `ROUND_HALF_UP` documenté.

## 3. Fichiers créés ou modifiés

Créations principales :

- `Mizzac/FundBoard/validators.py` : validation des codes devise et pays ;
- `Mizzac/FundBoard/services/valuation.py` : change, quote-part, valorisation et
  patrimoine net ;
- `Mizzac/FundBoard/services/performance.py` : performance Modified Dietz et
  ventilation des composantes ;
- `Mizzac/FundBoard/services/transactions.py` : insertion idempotente,
  appariement de transferts et classification des flux ;
- `Mizzac/FundBoard/tests/test_valuation.py` ;
- `Mizzac/FundBoard/tests/test_performance.py` ;
- `Mizzac/FundBoard/tests/test_transaction_services.py` ;
- `Mizzac/FundBoard/MODELE_CANONIQUE.md` : documentation du schéma, des signes,
  de la précision, de la propriété et de l'idempotence ;
- `RAPPORT_PHASE_3_FUNDBOARD.md` : présent compte rendu.

Modifications principales :

- `Mizzac/FundBoard/models.py` : remplacement du prototype par le modèle
  canonique ;
- `Mizzac/FundBoard/admin.py` : administration des nouvelles entités avec
  listes, filtres et recherches ;
- `Mizzac/FundBoard/migrations/0001_initial.py` : migration initiale canonique ;
- suppression des anciens `0002` à `0005` devenus sans objet sur une base
  neuve ;
- `Mizzac/FundBoard/views.py` : requêtes et contextes alignés sur comptes,
  instruments, positions, transactions et connexions ;
- templates `accounts.html`, `portfolio.html`, `transactions.html` et
  `fundboard.html` : champs canoniques et états de synchronisation ;
- `Mizzac/FundBoard/forms.py` : validation utilisateur explicite des devises ;
- tests modèles et vues existants : nouveaux champs et isolation des positions ;
- `README.md` et `OPERATIONS_DATABASE.md` : procédure de base neuve et
  incompatibilité assumée avec l'ancien prototype.

## 4. Migrations et impact sur les données

La nouvelle `FundBoard.0001_initial` crée quinze modèles et leurs contraintes,
index et relations. Elle s'applique avec succès sur une base SQLite vide.

Cette migration n'est volontairement pas compatible avec une base ayant déjà
enregistré l'ancien `FundBoard.0001` : le même numéro désignerait un schéma
différent. Cette décision serait interdite en présence de données réelles, mais
elle est ici conforme à l'autorisation explicite de repartir de zéro.

La base éventuellement présente dans le dépôt n'a pas été touchée. Les
validations ont utilisé des bases temporaires ou la base de test en mémoire.
Si une ancienne base réapparaît, il ne faut pas lancer `migrate` dessus : elle
doit être archivée puis traitée par un export/import dédié.

## 5. Commandes de validation exécutées

| Commande | Résultat |
|---|---|
| `manage.py migrate --noinput` sur une SQLite neuve dans `/tmp` | toutes les migrations appliquées ; `FundBoard.0001_initial` validée |
| `manage.py showmigrations FundBoard` | migration canonique unique marquée appliquée |
| `manage.py makemigrations --check --dry-run` | aucun changement détecté |
| `make ci` avec Django 5.2.17 | chaîne complète réussie |
| `python3 -m ruff check .` | aucun problème |
| `python3 -m compileall -q Mizzac` | succès |
| `manage.py check --settings=Mizzac.settings_test` | aucun problème |
| `pytest --cov --cov-report=term-missing` | 58 tests et 60 sous-tests réussis ; couverture totale 84,41 % |
| `python3 -Wd -m pytest -q` sous Django 6.1.1 | 58 tests et 60 sous-tests réussis, sans avertissement de dépréciation |
| `manage.py check --deploy` avec réglages HTTPS de production | aucun problème |
| `git diff --check` | aucune erreur d'espace ou de conflit |

Les nouveaux tests couvrent les contraintes de propriété, la précision déclarée,
les signes, les valeurs converties, les snapshots, les identifiants externes,
l'unicité fournisseur, les rejeux et conflits d'idempotence, les transferts
internes, les conversions, le patrimoine net et la performance.

## 6. Description des écrans concernés

- **Vue d'ensemble FundBoard** : soldes toujours séparés par devise, compteurs
  canoniques, dernières transactions sur `net_amount` et alerte lorsque des
  connexions sont périmées ou en erreur.
- **Comptes** : distinction manuel/synchronisé issue de la source et de la
  connexion, institution éventuelle et quote-part lorsqu'elle diffère de 100 %.
- **Portefeuille** : chaque carte représente le compte contenant ; les
  instruments et quantités sont listés comme positions à l'intérieur, avec la
  valeur et sa devise lorsqu'elles existent.
- **Transactions** : type canonique, instrument éventuel, quantité, montant net,
  devise propre à l'opération et filtres existants.
- **Modales** : création, modification et suppression des comptes et
  abonnements continuent d'utiliser les mêmes URL et comportements asynchrones.

Aucune capture visuelle automatisée n'a été produite. Les écrans sont validés
par les smoke tests de rendu, les assertions d'isolation utilisateur et les
tests fonctionnels des modales.

## 7. Risques, limites et dette technique restante

- SQLite ne garantit pas les 18 décimales de quantité à la lecture pour de très
  grands niveaux de précision, à cause de son affinité numérique. PostgreSQL
  est requis en production ; les calculs Python restent exacts dans les deux cas.
- Il n'existe aucune migration de reprise de l'ancien prototype. C'est une
  décision assumée et documentée, valable uniquement tant qu'aucune donnée
  réelle n'existe.
- La copropriété est pour l'instant une quote-part unique ; les propriétaires
  multiples nommés ne sont pas encore modélisés.
- Immobilier, prêts/passifs et engagements de private equity spécialisés ne
  sont pas encore modélisés. Ils doivent précéder leur CRUD de phase 4.
- Les services de calcul existent, mais le dashboard patrimonial consolidé ne
  doit pas afficher un total multi-devise tant qu'aucun taux réel daté n'est
  disponible. Cette intégration appartient à la phase 5.
- Les snapshots sont stockables mais pas encore planifiés automatiquement.
- `models.py` centralise encore le registre du schéma. Il devra être séparé par
  domaine lorsque les modèles immobiliers et prêts seront introduits, afin de
  ne pas devenir un module monolithique.
- Aucun connecteur ni appel réseau réel n'a été ajouté pendant cette phase.

## 8. Proposition exacte pour la phase suivante

Exécuter la phase 4 dans cet ordre :

1. ajouter les modèles spécialisés `RealEstate`, `Loan` et
   `PrivateEquityHolding`, avec valorisations datées et propriété testée ;
2. ajouter les formulaires et CRUD Tabler manuels pour comptes, instruments,
   positions, transactions, biens et prêts, en préférant l'archivage à la
   suppression ambiguë ;
3. définir un schéma JSON versionné et un classeur Excel avec les feuilles
   `README`, `Accounts`, `Instruments`, `Positions`, `Transactions`,
   `RealEstate`, `Loans` et les listes de valeurs autorisées ;
4. implémenter un dry-run strict qui détaille créations, mises à jour, doublons
   et erreurs par feuille/ligne/colonne ;
5. écrire l'import atomique avec empreinte SHA-256 et clés d'idempotence, puis
   l'annulation des lots non ambigus ;
6. ajouter les exports JSON, CSV et Excel en excluant systématiquement secrets
   et métadonnées sensibles ;
7. terminer par les tests d'import valide, partiel, invalide et dupliqué, les
   permissions à deux utilisateurs et une migration sur base vierge.

## 9. Questions nécessitant validation

Une décision est nécessaire avant l'écriture de l'import de phase 4 : valider
une stratégie **atomique par fichier**, recommandée ici. Après le dry-run, la
moindre ligne invalide annulerait tout le lot ; l'utilisateur corrigerait le
fichier puis le relancerait. Cette stratégie est plus simple à auditer et à
annuler qu'un succès partiel, au prix de bloquer les lignes valides tant qu'une
erreur subsiste.
