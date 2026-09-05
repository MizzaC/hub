# Ajouter un connecteur financier

## Frontière obligatoire

Un connecteur est un adaptateur de lecture. Il ne doit exposer aucune méthode de
trading, retrait, transfert ou modification distante. Les secrets proviennent
exclusivement de l'environnement ou d'un gestionnaire externe ; `Connection`
ne conserve qu'une `secret_reference` opaque et une configuration non sensible.

Les payloads fournisseur ne sont jamais écrits directement dans les modèles.
Ils sont convertis vers les objets immuables de
`FundBoard.integrations.connectors.base`, puis confiés à
`services.connectors`, qui valide chaque ligne et assure idempotence et succès
partiel.

## Étapes

1. Créer l'adaptateur sous `FundBoard/integrations/connectors/` en respectant
   l'interface `BaseConnector`.
2. Déclarer explicitement `provider_name`, `import_only` et les capacités de
   lecture. Limiter les délais HTTP et utiliser l'injection du client HTTP pour
   les tests.
3. Valider la configuration publique sans jamais accepter de token, mot de
   passe, cookie, PIN, code 2FA, seed ou clé privée dans un `JSONField`.
4. Mapper comptes, instruments, positions et transactions vers `SyncPayload`.
   Chaque identifiant distant stable alimente les clés d'idempotence.
5. Enregistrer l'adaptateur dans `integrations/connectors/registry.py` et son
   type d'institution dans `services.connectors.institution_for_provider`.
6. Ajouter le formulaire seulement pour les réglages non secrets. Référencer les
   variables secrètes dans `.env.example` avec une valeur vide.
7. Écrire des tests sans réseau : contrat, limites, erreurs publiques, payload
   invalide, déduplication, deuxième synchronisation, ligne invalide ignorée et
   absence de secret dans logs, base et interface.
8. Documenter consentement, révocation, périmètre exact, limites, fréquence,
   import de secours et procédure d'incident dans `CONNECTORS.md`.

## Critères d'acceptation

- permission distante strictement en lecture seule vérifiée ;
- synchronisation initiale et incrémentale idempotente ;
- une ligne invalide est rejetée sans annuler les lignes valides ;
- aucun payload brut ou secret persistant ;
- erreurs destinées à l'utilisateur expurgées ;
- statut, compteurs et corrélation visibles ;
- réseau entièrement mocké dans les tests ;
- déconnexion locale et procédure de révocation distante documentées.

Ne pas activer un adaptateur non officiel qui exige mot de passe, cookie de
session ou contournement de 2FA. Trade Republic titres reste donc un import
local de secours tant qu'une API officielle adaptée n'existe pas.

