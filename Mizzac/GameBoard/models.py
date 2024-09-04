from django.db import models
from django.contrib.auth.models import User

class TypeDeJeu(models.Model):
    nom = models.CharField(max_length=100)

    def __str__(self):
        return self.nom

class Jeu(models.Model):
    nom = models.CharField(max_length=100, primary_key=True)
    description = models.JSONField(default=list, blank=True)
    regles = models.JSONField(default=list, blank=True)
    variantes = models.JSONField(default=list, blank=True)
    astuces = models.JSONField(default=list, blank=True)
    type_de_jeu = models.ForeignKey(TypeDeJeu, on_delete=models.CASCADE, related_name="jeux")

    def __str__(self):
        return self.nom

class ProfilJoueur(models.Model):
    utilisateur = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nom_invite = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.utilisateur.username if self.utilisateur else self.nom_invite
    
class SkyJoSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    scores = models.JSONField(default=dict, blank=False)
    ranking = models.JSONField(default=list, blank=True)

class NavalBattleSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    game_grid = models.JSONField(default=list, blank=False)
    calling_shot = models.JSONField(default=list, blank=False) # format : 1A2 first number identify player and second part identify the location of shot
    ranking = models.JSONField(default=list, blank=True)
    
    
class TicTacToeSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    game_grid = models.JSONField(default=list, blank=False)
    users_actions = models.JSONField(default=list, blank=False) # format : 1A2 first number identify player and second part identify the location of symbol
    ranking = models.JSONField(default=list, blank=True)
    
    
class ChessSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    game_grid = models.JSONField(default=list, blank=False)
    users_actions = models.JSONField(default=list, blank=False) # format : 1A2 first number identify player and second part identify the location of move
    ranking = models.JSONField(default=list, blank=True)
    
    
# class Partie(models.Model):
#     jeu = models.ForeignKey(Jeu, on_delete=models.CASCADE, related_name="parties")
#     date_debut = models.DateTimeField(auto_now_add=True)
#     date_fin = models.DateTimeField(blank=True, null=True)
#     joueurs = models.ManyToManyField(ProfilJoueur, through='Participation')

#     def __str__(self):
#         return f"{self.jeu.nom} - {self.date_debut}"

# class Participation(models.Model):
#     joueur = models.ForeignKey(ProfilJoueur, on_delete=models.CASCADE)
#     partie = models.ForeignKey(Partie, on_delete=models.CASCADE)
#     score = models.IntegerField(default=0)

#     def __str__(self):
#         return f"{self.joueur} - {self.partie} - Score: {self.score}"

# class HistoriquePartie(models.Model):
#     partie = models.OneToOneField(Partie, on_delete=models.CASCADE, related_name="historique")
#     date_archive = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Historique de {self.partie}"

# class Statistique(models.Model):
#     joueur = models.ForeignKey(ProfilJoueur, on_delete=models.CASCADE, related_name="statistiques")
#     jeu = models.ForeignKey(Jeu, on_delete=models.CASCADE, related_name="statistiques")
#     nombre_victoires = models.IntegerField(default=0)
#     pourcentage_reussite = models.FloatField(default=0.0)

#     def __str__(self):
#         return f"Stats de {self.joueur} pour {self.jeu.nom}"
