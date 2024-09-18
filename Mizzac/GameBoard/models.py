# models.py de GameBoard
from django.db import models
from django.contrib.auth.models import User
from DashBoard.models import Dashboard
from django.utils.text import slugify

class Categorie(models.Model):
    nom = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.nom

def get_upload_path(instance, filename):
    # Use the name of the game to make the directory name
    return f'GameBoard/jeux/{instance.nom}/{filename}'

class Jeu(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField()
    categories = models.ManyToManyField('Categorie', related_name='jeux')
    couverture = models.ImageField(upload_to=get_upload_path, default='GameBoard/jeux/default.png')
    slug = models.SlugField(unique=True, blank=True)  # Champ slug ajouté

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)  # Génère un slug basé sur le nom
        super(Jeu, self).save(*args, **kwargs)

    def __str__(self):
        return self.nom

class Joueur(models.Model):
    nom = models.CharField(max_length=255, unique=True)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    profil = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.nom

class Partie(models.Model):
    jeu = models.ForeignKey(Jeu, on_delete=models.CASCADE)
    tableau_de_bord = models.ForeignKey(Dashboard, on_delete=models.CASCADE)  # Utilisation de l'import direct
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=50, choices=[
        ('en cours', 'En cours'),
        ('terminée', 'Terminée')
    ])

    def __str__(self):
        return f"{self.jeu} - {self.date_creation}"

class Score(models.Model):
    partie = models.ForeignKey(Partie, on_delete=models.CASCADE)
    joueur = models.ForeignKey(Joueur, on_delete=models.CASCADE)
    points = models.IntegerField()
    tour = models.IntegerField()

    def __str__(self):
        return f"{self.joueur} - {self.points} points"

class HistoriquePartie(models.Model):
    partie = models.ForeignKey(Partie, on_delete=models.CASCADE)
    date_fin = models.DateTimeField(null=True, blank=True)
    gagnant = models.ForeignKey(Joueur, on_delete=models.CASCADE)
    statistiques = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Historique - {self.partie}"
