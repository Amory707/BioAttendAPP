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
			"roles": [str(role_admin.pk)],
		}

		response = self.client.post(reverse("Employee:utilisateur_create"), payload)

		self.assertEqual(response.status_code, 302)
		self.assertRedirects(response, reverse("Employee:utilisateur_list"))
		created_user = Utilisateur.objects.get(email="jane.smith@example.com")
		self.assertEqual(created_user.username, "janesmith")
		self.assertTrue(
			RoleUtilisateur.objects.filter(utilisateur=created_user, role=role_admin).exists()
		)

	def test_create_utilisateur_accepts_multiple_roles(self):
		role_employe = self._create_role("employé")
		role_admin = self._create_role("admin")
		request_user = self._create_user("owner-multi")
		self.client.force_login(request_user)

		payload = {
			"first_name": "Ari",
			"last_name": "Dual",
			"email": "ari.dual@example.com",
			"departement": "Ops",
			"roles": [str(role_employe.pk), str(role_admin.pk)],
		}

		response = self.client.post(reverse("Employee:utilisateur_create"), payload)

		self.assertEqual(response.status_code, 302)
		created_user = Utilisateur.objects.get(email="ari.dual@example.com")
		assigned_roles = set(
			RoleUtilisateur.objects.filter(utilisateur=created_user).values_list("role__nom", flat=True)
		)
		self.assertEqual(assigned_roles, {"employé", "admin"})

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
		self.assertContains(response, "Pointage")

	def test_statistiques_analytique_renders_global_metrics(self):
		user = self._create_user("stats-admin")
		target = self._create_user("stats-target", first_name="Lina", last_name="Ops")
		self.client.force_login(user)

		Pointage.objects.create(
			utilisateur=target,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.88,
		)

		response = self.client.get(reverse("Employee:statistiques_analytique"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Analytique")
		self.assertContains(response, "Performance par employé")
		self.assertContains(response, reverse("Employee:statistiques_utilisateur", kwargs={"utilisateur_id": target.pk}))

	def test_statistiques_utilisateur_shows_person_scope(self):
		user = self._create_user("scope-admin")
		target = self._create_user("scope-target", first_name="Rita", last_name="Data")
		self.client.force_login(user)

		Pointage.objects.create(
			utilisateur=target,
			statut="VALIDE",
			type="SORTIE",
			horodatage=timezone.now(),
			score_confiance=0.91,
		)

		response = self.client.get(reverse("Employee:statistiques_utilisateur", kwargs={"utilisateur_id": target.pk}))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Analyse ciblée: Rita Data")
		self.assertContains(response, "Retour global")

	def test_statistiques_problemes_lists_recognition_issues(self):
		user = self._create_user("problem-admin")
		target = self._create_user("problem-target", first_name="Nora", last_name="Face")
		self.client.force_login(user)

		Alerte.objects.create(
			utilisateur=None,
			type="UTILISATEUR_INCONNU",
			description="Visage inconnu detecte",
			statut="NOUVELLE",
		)
		Alerte.objects.create(
			utilisateur=target,
			type="ECHEC_RECONNAISSANCE",
			description="Distance trop elevee",
			statut="VUE",
		)

		response = self.client.get(reverse("Employee:statistiques_problemes"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Journal sécurité de reconnaissance")
		self.assertContains(response, "UTILISATEUR_INCONNU")
		self.assertContains(response, "ECHEC_RECONNAISSANCE")
		self.assertEqual(len(response.context["problem_alerts"]), 2)

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

	def test_pointage_export_csv_returns_filtered_valid_rows(self):
		user = self._create_user("csv-pointage-admin")
		target = self._create_user("csv-pointage-target", first_name="Mina", last_name="Flow")
		self.client.force_login(user)

		Pointage.objects.create(
			utilisateur=target,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.95,
		)
		Pointage.objects.create(
			utilisateur=target,
			statut="NON_VALIDE",
			type="SORTIE",
			horodatage=timezone.now(),
			score_confiance=0.12,
		)

		response = self.client.get(reverse("Employee:pointage_export_csv"), {"tab": "pointage"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response["Content-Type"], "text/csv")
		content = response.content.decode("utf-8")
		self.assertIn("ID Pointage,Date Heure,Username,Nom,Prenom,Type,Statut,Score IA", content)
		self.assertIn("VALIDE", content)
		self.assertNotIn("NON_VALIDE", content)

	def test_pointage_export_csv_user_scope_uses_utilisateur_filter(self):
		user = self._create_user("csv-pointage-scope")
		target = self._create_user("target-scope", first_name="Zoe", last_name="Core")
		other = self._create_user("other-scope", first_name="Yan", last_name="Ops")
		self.client.force_login(user)

		Pointage.objects.create(
			utilisateur=target,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.83,
		)
		Pointage.objects.create(
			utilisateur=other,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.81,
		)

		response = self.client.get(
			reverse("Employee:pointage_export_utilisateur_csv", kwargs={"utilisateur_id": target.pk}),
			{"tab": "pointage"},
		)

		self.assertEqual(response.status_code, 200)
		content = response.content.decode("utf-8")
		self.assertIn("target-scope", content)
		self.assertNotIn("other-scope", content)
