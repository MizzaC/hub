# Imports et exports FundBoard — schéma 1.0

## Principe

Les formats JSON et Excel partagent le même schéma versionné `1.0`. Les modèles
téléchargeables contiennent une ligne d'exemple à remplacer ou supprimer.
Aucun connecteur externe n'est requis.

L'import utilise un **succès partiel par ligne** :

- une ligne valide est créée ou mise à jour dans une transaction dédiée ;
- une ligne invalide est intégralement annulée et n'est jamais importée ;
- les autres lignes continuent d'être traitées ;
- le rapport indique feuille/section, ligne, colonne, code et message ;
- une prévisualisation exécute les mêmes contrôles puis annule toutes les
  écritures.

Les lignes sont traitées dans l'ordre logique comptes, instruments, prêts,
positions, transactions puis immobilier, indépendamment de l'ordre des feuilles.

## Formats

Taille maximale : 5 Mio. Les extensions acceptées sont `.json` et `.xlsx`.
Le JSON doit être encodé en UTF-8 et commencer par :

```json
{
  "schema_version": "1.0",
  "accounts": [],
  "instruments": [],
  "positions": [],
  "transactions": [],
  "real_estate": [],
  "loans": []
}
```

Le classeur contient `README`, `Accounts`, `Instruments`, `Positions`,
`Transactions`, `RealEstate`, `Loans` et une feuille masquée `Lists`. La version
est portée par `README!B1`. Les en-têtes inconnus, formules, macros et liens
externes sont refusés. La taille décompressée est limitée à 50 Mio.

## Références et champs obligatoires

| Section | Champs obligatoires |
|---|---|
| Accounts | `manual_reference`, `name`, `category`, `currency` |
| Instruments | `manual_reference`, `name`, `instrument_type`, `currency` |
| Positions | `account_reference`, `instrument_reference`, `quantity`, `value_currency` |
| Transactions | `account_reference`, `transaction_type`, `net_amount`, `currency`, `executed_at` |
| RealEstate | `manual_reference`, `name`, `property_type`, `currency`, `purchase_price`, `estimated_value`, `valuation_date` |
| Loans | `manual_reference`, `name`, `loan_type`, `currency`, `original_principal`, `outstanding_principal`, `nominal_rate`, `duration_months`, `start_date` |

Les `manual_reference` sont des identifiants privés et stables choisis par
l'utilisateur. Les positions et transactions les réutilisent via
`account_reference` et `instrument_reference`; l'immobilier utilise
`loan_reference`. Une ligne qui référence un objet absent ou appartenant à un
autre utilisateur est rejetée.

Une transaction peut fournir `idempotency_key`. Sans cette valeur, une clé
déterministe est dérivée de son contenu. La convention de signe de
`net_amount` est celle de `MODELE_CANONIQUE.md`.

## Déduplication, historique et annulation

L'empreinte SHA-256 du fichier interdit le double import pour un utilisateur.
Une ligne inchangée est comptée comme ignorée. L'historique conserve uniquement
le nom, le format, l'empreinte, les compteurs, les erreurs et un journal des
champs financiers autorisés ; le fichier brut n'est pas stocké.

Un lot peut être annulé si chaque objet est encore exactement dans l'état laissé
par l'import et si aucune donnée extérieure au lot n'en dépend. Sinon,
l'annulation entière est refusée. Après une annulation réussie, le même fichier
peut être importé de nouveau.

Les imports, leurs annulations et les exports alimentent aussi la piste d'audit
financière. Elle ne conserve ni contenu de fichier, ni valeur financière brute,
ni donnée de formulaire.

## Exports et sécurité

L'export complet ou par catégorie est disponible en JSON et Excel. Le CSV porte
une seule catégorie. Les exports sont limités aux données de l'utilisateur et
excluent notamment mots de passe, tokens, cookies, références de secrets,
charges utiles fournisseur, `metadata`, curseurs de synchronisation et données
des autres utilisateurs. Les cellules textuelles dangereuses sont neutralisées
pour éviter leur exécution comme formule dans un tableur.

L'adresse immobilière reste une donnée privée : elle n'apparaît pas dans les
listes ni dans les rapports d'erreur, mais figure dans l'export authentifié du
propriétaire afin de permettre une sauvegarde complète.
