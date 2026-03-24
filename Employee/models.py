from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from pgvector.django import VectorField

class Role(models.Model):
    ID_Role = models.AutoField(primary_key=True)
    Nom = models.CharField(max_length=10, choices=[('ADMIN', 'Admin'), ('EMPLOYE', 'Employé')])

    class Meta:
        db_table = 'Rôle'
        verbose_name = "Rôle"

class Utilisateur(models.Model):  
    ID_Utilisateur = models.AutoField(primary_key=True)
    Login_Utilisateur = models.CharField(max_length=255, unique=True, null=True, blank=True)
    Nom = models.CharField(max_length=255)
    Prenom = models.CharField(max_length=255) 
    Email = models.EmailField(unique=True, max_length=255)
    Mot_de_passe = models.CharField(max_length=255) 
    Embedding_facial = VectorField(dimensions=128, null=True, blank=True)
    Departement = models.CharField(max_length=50, null=True, blank=True)
    Date_debut = models.DateField(auto_now_add=True)
    Date_fin = models.DateField(null=True, blank=True)
    
    roles = models.ManyToManyField(Role, related_name="utilisateurs")

    class Meta:
        db_table = 'Utilisateur' 
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.Prenom} {self.Nom}"

class Pointage(models.Model):
    ID_Pointage = models.AutoField(primary_key=True)
    statut = models.CharField(max_length=20, choices=[('Validé', 'Validé'), ('Non validé', 'Non validé')], default='Validé')
    horodatage = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=10, choices=[('ENTREE', 'Entrée'), ('SORTIE', 'Sortie')])
    score_confiance = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    
   
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, db_column='ID_Utilisateur', related_name='pointages', null=True, blank=True)
    class Meta:
        db_table = 'Pointage'


class Alerte(models.Model):
    ID_Alerte = models.AutoField(primary_key=True) # Clé primaire selon le MLD 
    Type = models.CharField(max_length=50) # Type d'alerte (RETARD, ABSENCE, etc.) 
    Description = models.TextField() # Description détaillée 
    Date_creation = models.DateTimeField(auto_now_add=True) # Date et heure de création 
    Statut = models.CharField(max_length=20, default='NOUVELLE') # NOUVELLE, VUE, TRAITÉE 
    
    # Relations conformes au MLD 
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, db_column='ID_Utilisateur')
    pointage = models.ForeignKey(Pointage, on_delete=models.SET_NULL, null=True, db_column='ID_Pointage')

    class Meta:
        db_table = 'Alertes' # Nom exact dans Supabase 
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"