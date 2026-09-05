# Version Django retenue

Le projet utilise uniquement **Django 6.1.1** sur Python 3.12. Il n'existe plus
de matrice séparée Django 5.2 / Django-next dans le dépôt.

Toutes les dépendances de développement et de production incluent
`requirements.txt`, qui verrouille cette version exacte. La suite locale se
lance avec :

```bash
python3 -m pip install -r requirements-dev.txt
make ci
```

Une future montée de version devra être décidée explicitement, suivie d'une
lecture des notes de publication et d'une validation complète des migrations,
tests, avertissements et contrôles de déploiement.

Documentation : <https://docs.djangoproject.com/en/6.1/>
