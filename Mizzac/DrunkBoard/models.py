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
    taux_alcool = models.DecimalField(max_digits=4, decimal_places=1)
    annee = models.IntegerField(blank=False)
    histoire = models.TextField()
    Pays = models.CharField(max_length=20)
    Region = models.CharField(max_length=20)
    caracteristiques = models.JSONField()

class Degustation(models.Model):
    boisson = models.ForeignKey(Boisson, on_delete=models.CASCADE)
    note = models.JSONField() # json avec comme clés des noms de notes et comme valeurs des notes allant de 0 à 5 (ex: {"aromes": 3, "texture": 4, "couleur": 2, etc}) 
    commentaire = models.TextField() # commentaire général
    date = models.DateField(auto_now_add=True) # date de la dégustation
    observations = models.JSONField() # json avec clé aromes, texture, couleur, etc contenant des listes de notes comme les aromes etc
    
class Arome_Whisky(models.Model):
    nom = models.CharField(max_length=40)
    famille_aromatique = models.CharField(max_length=30)
    sous_famille_aromatique = models.CharField(max_length=30)
    color = models.CharField(max_length=7)

class Arome_Vin(models.Model):
    nom = models.CharField(max_length=40)
    famille_aromatique = models.CharField(max_length=30)
    sous_famille_aromatique = models.CharField(max_length=30)
    color = models.CharField(max_length=7)
    
class Texture_Vin(models.Model):
    texture = models.CharField(max_length=30)
    
class Texture_Whisky(models.Model):
    texture = models.CharField(max_length=30)
    
class Couleur_Vin(models.Model):
    nom = models.CharField(max_length=30)
    cat_vin = models.CharField(max_length=30)
    color = models.CharField(max_length=30)
    echelle = models.CharField(max_length=30)
    
class Couleur_Whisky(models.Model):
    nom = models.CharField(max_length=30)
    color = models.CharField(max_length=30)
    echelle = models.CharField(max_length=30)