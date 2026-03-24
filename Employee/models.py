from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from pgvector.django import VectorField

class Employee(models.Model):
    ID_Utilisateur = models.AutoField(primary_key=True)
    Nom = models.CharField(max_length=255)
    Prenom = models.CharField(max_length=255)
    Email = models.EmailField(unique=True, max_length=255)
    
   
    Login_Utilisateur = models.CharField(max_length=255, unique=True, null=True, blank=True)
    Password = models.CharField(max_length=255) # Mot de passe hashé 
    
    # Données biométriques (Vecteur de 128 ou 512 dimensions )
    Embedding_facial = VectorField(dimensions=128, null=True, blank=True)
    
   
    Departement = models.CharField(max_length=50, null=True, blank=True)
    Date_debut = models.DateField(auto_now_add=True)
    Date_fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"

    def __str__(self):
        return f"{self.Prenom} {self.Nom} ({self.Departement})"




class Pointage(models.Model):
    # Choix pour les champs ENUM 
    TYPE_CHOICES = [('ENTREE', 'Entrée'), ('SORTIE', 'Sortie')]
    STATUT_CHOICES = [('Validé', 'Validé'), ('Non validé', 'Non validé')]

    # Relation avec l'employé (Clé étrangère)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='pointages')
    
    # Détails du pointage selon votre MLD
    horodatage = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='Validé')
    score_confiance = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)], help_text="Précision de l'IA (0.0 à 1.0)")

    class Meta:
        verbose_name = "Pointage"
        verbose_name_plural = "Pointages"
        ordering = ['-horodatage'] # Les plus récents en premier

    def __str__(self):
        return f"{self.employee.Nom} - {self.type} - {self.horodatage.strftime('%d/%m/%Y %H:%M')}"