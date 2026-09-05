# Audit de sécurité — phase 10

Date : 5 septembre 2026  
Périmètre : code Django, modèles financiers, imports, connecteurs, paramètres,
automatisation, dépendances déclarées et ressources front-end.

## Modèle de menace

Le déploiement visé est personnel, pour un seul propriétaire, éventuellement
accessible derrière un proxy HTTPS. Les actifs sensibles sont données
financières, sessions Django, secrets de connecteurs et sauvegardes. Les menaces
principales sont exposition accidentelle, import hostile, accès croisé entre
utilisateurs, fuite dans les logs, connecteur trop permissif et restauration
non vérifiée.

## Constats corrigés ou validés

- `DEBUG`, clé secrète, hôtes, origines CSRF et base viennent de
  l'environnement. `.env`, bases, médias, sauvegardes usuelles et logs sont
  ignorés par Git.
- Toutes les vues financières sensibles exigent une session et filtrent par
  propriétaire. Les écritures passent par POST avec protection CSRF. Les tests
  couvrent les accès croisés sur patrimoine, imports, connecteurs, simulations,
  paper trading et exploitation.
- Les connecteurs sont limités à la lecture. Aucun secret n'est stocké dans les
  modèles ; Trade Republic live non officiel reste désactivé.
- Les imports limitent format et taille, neutralisent les formules Excel,
  valident chaque ligne et n'importent pas une ligne invalide.
- Les sorties JSON vers JavaScript utilisent `json_script`. Les bibliothèques
  front-end sont versionnées localement sans CDN.
- Les en-têtes `nosniff`, `DENY`, politique de référent et restriction des
  capacités caméra/micro/géolocalisation/paiement/USB sont appliqués. Cookies
  HTTP-only et `SameSite=Lax` sont explicites ; HTTPS, cookies Secure et HSTS
  restent activables uniquement après configuration correcte du proxy.
- Les logs acceptent seulement quelques champs de contexte et expurgent les
  motifs courants de token, secret, mot de passe, cookie, PIN et 2FA, y compris
  dans les exceptions.
- Les subprocess de sauvegarde PostgreSQL utilisent une liste d'arguments sans
  shell. Le mot de passe éventuel passe par l'environnement de `pg_dump`, jamais
  par la ligne de commande.
- Les sauvegardes SQLite sont cohérentes, en mode `0600`, signées par SHA-256 et
  vérifiées avant toute restauration. Une destination existante ou la base
  active ne peut pas être écrasée.
- Les versions Python et JavaScript sont verrouillées. La CI exécute tests,
  couverture, Ruff, compilation, contrôle des migrations, `pip check` et
  reconstruction reproductible des ressources.

Une recherche statique des motifs usuels n'a trouvé aucune clé privée ou jeton
réel. Les occurrences de mots de passe/tokens sont limitées aux tests de
redaction et aux noms de paramètres attendus.

## Risques résiduels

- Aucune politique CSP stricte n'est encore activée, car plusieurs templates
  utilisent du JavaScript inline. Leur migration vers des fichiers statiques et
  des nonces est recommandée avant une exposition Internet.
- Les dépendances sont verrouillées mais l'analyse de CVE dépend d'un service ou
  outil externe. Elle doit être exécutée régulièrement dans un environnement
  ayant accès aux avis de sécurité ; les mises à jour restent manuelles afin de
  conserver Django 6.1.1.
- Le chiffrement au repos dépend du système d'exploitation, de PostgreSQL et du
  support de sauvegarde. L'application ne chiffre pas elle-même la base.
- Le serveur de développement n'est pas adapté à une exposition réseau. La
  terminaison TLS, la limitation de débit, le pare-feu et la rotation des logs
  appartiennent au déploiement.
- La redaction est une défense secondaire : aucun appel ne doit transmettre un
  secret au logger en premier lieu.

## Décision de sortie

Aucun défaut bloquant n'a été identifié pour un usage personnel local ou
derrière un proxy HTTPS correctement configuré. Une exposition directe à
Internet reste déconseillée tant qu'un serveur de production, une CSP et une
politique de mises à jour de sécurité ne sont pas en place.

