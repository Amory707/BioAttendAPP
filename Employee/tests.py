from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, RoleUtilisateur, Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage

from .views import FiltreBiometrique, _validate_photo_uploads


@override_settings(SECRET_KEY='test-api-secret')
class EmployeeAppTests(TestCase):
	def tearDown(self):
		# Nettoyage explicite demande: suppression de tout ajout en base.
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Utilisateur.objects.all().delete()
		Role.objects.all().delete()

	def _create_role(self, nom="admin"):
		return Role.objects.create(nom=nom)

	def _create_user(self, username, first_name="John", last_name="Doe", **extra):
		defaults = {
			"email": f"{username}@example.com",
			"password": "test-pass-123",
			"first_name": first_name,
			"last_name": last_name,
		}
		defaults.update(extra)
		return Utilisateur.objects.create_user(username=username, **defaults)

	def test_validate_photo_uploads_rejects_more_than_five_images(self):
		photos = [
			SimpleUploadedFile(f"photo_{i}.jpg", b"fake-image", content_type="image/jpeg")
			for i in range(6)
		]

		error = _validate_photo_uploads(photos)

		self.assertIsNotNone(error)
		self.assertIn("maximum", error.lower())

	def test_validate_photo_uploads_rejects_non_image_file(self):
		photos = [
			SimpleUploadedFile("notes.txt", b"not-an-image", content_type="text/plain"),
		]

		error = _validate_photo_uploads(photos)

		self.assertEqual(error, "Seuls les fichiers image sont autorises.")

	def test_filtre_biometrique_filters_enrolled_and_non_enrolled(self):
		enrolled = self._create_user("enrolled", embedding_facial=[0.0] * 512)
		non_enrolled = self._create_user("nonenrolled", embedding_facial=None)

		enroles = FiltreBiometrique.filtrer_queryset(Utilisateur.objects.all(), "enrole")
		non_enroles = FiltreBiometrique.filtrer_queryset(Utilisateur.objects.all(), "non_enrole")

		self.assertIn(enrolled, enroles)
		self.assertNotIn(non_enrolled, enroles)
		self.assertIn(non_enrolled, non_enroles)
		self.assertNotIn(enrolled, non_enroles)

	def test_utilisateur_list_requires_authentication(self):
		response = self.client.get(reverse("Employee:utilisateur_list"))
		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse("login"), response.url)

	def test_utilisateur_list_filters_by_search(self):
		user = self._create_user("manager", first_name="Alice", last_name="Martin")
		self._create_user("other", first_name="Bob", last_name="Durand")
		self.client.force_login(user)

		response = self.client.get(reverse("Employee:utilisateur_list"), {"q": "martin"})

		self.assertEqual(response.status_code, 200)
		utilisateurs = list(response.context["utilisateurs"])
		self.assertEqual(len(utilisateurs), 1)
		self.assertEqual(utilisateurs[0].username, "manager")

	def test_create_utilisateur_creates_employee_and_redirects(self):
		role_admin = self._create_role("admin")
		request_user = self._create_user("owner")
		self.client.force_login(request_user)

		payload = {
			"first_name": "Jane",
			"last_name": "Smith",
			"email": "jane.smith@example.com",
			"departement": "IT",
			"role": str(role_admin.pk),
		}

		response = self.client.post(reverse("Employee:utilisateur_create"), payload)

		self.assertEqual(response.status_code, 302)
		self.assertRedirects(response, reverse("Employee:utilisateur_list"))
		created_user = Utilisateur.objects.get(email="jane.smith@example.com")
		self.assertEqual(created_user.username, "janesmith")
		self.assertTrue(
			RoleUtilisateur.objects.filter(utilisateur=created_user, role=role_admin).exists()
		)

	def test_pointage_list_filters_by_type(self):
		user = self._create_user("pointage-user")
		self.client.force_login(user)

		Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.9,
		)
		Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			type="SORTIE",
			horodatage=timezone.now() - timedelta(hours=1),
			score_confiance=0.8,
		)

		response = self.client.get(reverse("Employee:pointage_list"), {"type": "ENTREE"})

		self.assertEqual(response.status_code, 200)
		pointages = list(response.context["pointages"])
		self.assertEqual(len(pointages), 1)
		self.assertEqual(pointages[0].type, "ENTREE")

	def test_alerte_list_filters_by_status(self):
		user = self._create_user("alert-user")
		self.client.force_login(user)

		Alerte.objects.create(
			utilisateur=user,
			type="RETARD",
			description="Retard detecte",
			statut="NOUVELLE",
		)
		Alerte.objects.create(
			utilisateur=user,
			type="ABSENCE",
			description="Absence justifiee",
			statut="VUE",
		)

		response = self.client.get(reverse("Employee:alerte_list"), {"statut": "NOUVELLE"})

		self.assertEqual(response.status_code, 200)
		alertes = list(response.context["alertes"])
		self.assertEqual(len(alertes), 1)
		self.assertEqual(alertes[0].statut, "NOUVELLE")

	def test_delete_utilisateur_post_removes_employee(self):
		request_user = self._create_user("deleter")
		target_user = self._create_user("target")
		self.client.force_login(request_user)

		response = self.client.post(
			reverse("Employee:utilisateur_delete", kwargs={"utilisateur_id": target_user.pk})
		)

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Utilisateur.objects.filter(pk=target_user.pk).exists())

	def test_export_csv_returns_expected_columns(self):
		user = self._create_user("csv-user", first_name="Iris", last_name="Nde")
		self.client.force_login(user)

		response = self.client.get(reverse("Employee:exporter_csv"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response["Content-Type"], "text/csv")
		content = response.content.decode("utf-8")
		self.assertIn("ID,Nom,Pr\u00e9nom,Email,D\u00e9partement", content)
		self.assertIn("Iris", content)
