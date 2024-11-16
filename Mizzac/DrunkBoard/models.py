from django.db import models

# class Categorie(models.Model):
#     nom = models.CharField(max_length=100)

# class FamilleAromatique(models.Model):
#     nom = models.CharField(max_length=100)

# class TypeArome(models.Model):
#     nom = models.CharField(max_length=100)

# class SousTypeArome(models.Model):
#     nom = models.CharField(max_length=100)
#     type_arome = models.ForeignKey(TypeArome, on_delete=models.CASCADE)

# class Arome(models.Model):
#     nom = models.CharField(max_length=100)
#     type = models.ForeignKey(TypeArome, on_delete=models.CASCADE)
#     sous_type = models.ForeignKey(SousTypeArome, on_delete=models.CASCADE)
#     famille_aromatique = models.ForeignKey(FamilleAromatique, on_delete=models.CASCADE)

# class Texture(models.Model):
#     sucre = models.IntegerField()
#     acidite = models.IntegerField()
#     alcool = models.IntegerField()
#     tanins = models.IntegerField()

class Boisson(models.Model):
    nom = models.CharField(max_length=100, blank=False)
    categorie = models.CharField(max_length=100, blank=False)
    annee = models.IntegerField(blank=False)
    histoire = models.TextField()
    Pays = models.CharField(max_length=20)
    Region = models.CharField(max_length=20)
    caracteristiques = models.JSONField()

class Degustation(models.Model):
    boisson = models.ForeignKey(Boisson, on_delete=models.CASCADE)
    note = models.JSONField()
    commentaire = models.TextField()
    date = models.DateField(auto_now_add=True)
    observations = models.JSONField() # json avec clé aromes, texture, couleur, etc contenant des listes de notes comme les aromes etc
    
class Arome(models.Model):
    nom = models.CharField(max_length=40)
    famille_aromatique = models.CharField(max_length=30)
    sous_famille_aromatique = models.CharField(max_length=30)
