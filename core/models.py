import uuid
from django.db import models
from pgvector.django import VectorField


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(
        max_length=20,
        choices=[("ADMIN", "ADMIN"), ("EMPLOYE", "EMPLOYE")],
    )

    class Meta:
        db_table = "role"

    def __str__(self):
        return self.nom


class Utilisateur(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    login_utilisateur = models.CharField(max_length=255, unique=True)
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    mot_de_passe = models.CharField(max_length=255)
    embedding_facial = VectorField(dimensions=384, null=True, blank=True)
    departement = models.CharField(max_length=50, blank=True, null=True)
    date_debut = models.DateField()
    date_fin = models.DateField(blank=True, null=True)
    roles = models.ManyToManyField(
        Role,
        through="RoleUtilisateur",
        related_name="utilisateurs",
    )

    class Meta:
        db_table = "utilisateur"

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class RoleUtilisateur(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_utilisateurs",
    )
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="role_utilisateurs",
    )

    class Meta:
        db_table = "role_utilisateur"
        unique_together = ("role", "utilisateur")

    def __str__(self):
        return f"{self.utilisateur} - {self.role}"


class Pointage(models.Model):
    STATUT_CHOICES = [("VALIDE", "Validé"), ("NON_VALIDE", "Non validé")]
    TYPE_CHOICES = [("ENTREE", "ENTREE"), ("SORTIE", "SORTIE")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES)
    horodatage = models.DateTimeField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    score_confiance = models.FloatField()
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="pointages",
    )

    class Meta:
        db_table = "pointage"

    def __str__(self):
        return f"{self.utilisateur} - {self.type} @ {self.horodatage}"


class Alerte(models.Model):
    STATUT_CHOICES = [
        ("NOUVELLE", "NOUVELLE"),
        ("VUE", "VUE"),
        ("TRAITEE", "TRAITEE"),
    ]
    TYPE_CHOICES = [
        ("RETARD", "RETARD"),
        ("ABSENCE", "ABSENCE"),
        ("UTILISATEUR_INCONNU", "UTILISATEUR_INCONNU"),
        ("ECHEC_RECONNAISSANCE", "ECHEC_RECONNAISSANCE"),
        ("DOUBLE_POINTAGE", "DOUBLE_POINTAGE"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    description = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="NOUVELLE")
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alertes",
    )
    pointage = models.ForeignKey(
        Pointage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alertes",
    )

    class Meta:
        db_table = "alerte"

    def __str__(self):
        return f"[{self.statut}] {self.type} ({self.id})"
