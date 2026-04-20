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

	def test_create_utilisateur_rejects_multiple_roles(self):
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

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Un seul rôle peut être attribué")
		self.assertFalse(Utilisateur.objects.filter(email="ari.dual@example.com").exists())

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

	def test_statistiques_show_prestations_tab_before_pointage(self):
		user = self._create_user("stats-tabs-admin")
		self.client.force_login(user)

		response = self.client.get(reverse("Employee:pointage_list"))

		self.assertEqual(response.status_code, 200)
		content = response.content.decode("utf-8")
		self.assertTrue(content.find("Prestations") < content.find("Pointage"))

	def test_statistiques_prestations_general_view_uses_employee_focused_chart(self):
		user = self._create_user("stats-prestations-general-admin")
		target_one = self._create_user("stats-prestations-emp-one", first_name="Mila", last_name="Clock")
		target_two = self._create_user("stats-prestations-emp-two", first_name="Noa", last_name="Time")
		self.client.force_login(user)

		now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
		Pointage.objects.create(utilisateur=target_one, statut="VALIDE", type="ENTREE", horodatage=now, score_confiance=0.93)
		Pointage.objects.create(utilisateur=target_one, statut="VALIDE", type="SORTIE", horodatage=now.replace(hour=17, minute=0), score_confiance=0.91)
		Pointage.objects.create(utilisateur=target_two, statut="VALIDE", type="ENTREE", horodatage=now.replace(hour=9, minute=0), score_confiance=0.92)
		Pointage.objects.create(utilisateur=target_two, statut="VALIDE", type="SORTIE", horodatage=now.replace(hour=15, minute=0), score_confiance=0.90)

		response = self.client.get(reverse("Employee:statistiques_prestations"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Heures prestées par employé")
		self.assertContains(response, "Mila Clock")
		self.assertContains(response, "Noa Time")
		self.assertIn("Mila Clock", response.context["prestations_chart_json"])

	def test_statistiques_prestations_renders_history_chart_and_csv(self):
		user = self._create_user("stats-prestations-admin")
		target = self._create_user("stats-prestations-target", first_name="Mila", last_name="Clock")
		self.client.force_login(user)

		now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
		Pointage.objects.create(
			utilisateur=target,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now,
			score_confiance=0.93,
		)
		Pointage.objects.create(
			utilisateur=target,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=17, minute=30),
			score_confiance=0.91,
		)

		response = self.client.get(reverse("Employee:statistiques_prestations"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Historique des heures prestées")
		self.assertContains(response, "Graphique des heures prestées")
		self.assertContains(response, "prestationsChart")
		self.assertContains(response, reverse("Employee:prestations_export_csv"))
		self.assertContains(response, "Employé")
		self.assertContains(response, "Mila Clock")
		self.assertContains(response, "Sessions validées aujourd'hui")

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
		)
		Alerte.objects.create(
			utilisateur=target,
			type="ECHEC_RECONNAISSANCE",
			description="Distance trop elevee",
		)

		response = self.client.get(reverse("Employee:statistiques_problemes"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Journal sécurité de reconnaissance")
		self.assertContains(response, "Utilisateur inconnu")
		self.assertContains(response, "Visage non détecté")
		self.assertEqual(len(response.context["problem_alerts"]), 2)

	def test_statistiques_utilisateur_problemes_includes_unassigned_device_alerts(self):
		admin = self._create_user("problem-scope-admin")
		target = self._create_user("problem-scope-target", first_name="Lina", last_name="Scope")
		self.client.force_login(admin)

		Alerte.objects.create(
			utilisateur=target,
			type="ECHEC_RECONNAISSANCE",
			description="Echec rattache utilisateur",
		)
		Alerte.objects.create(
			utilisateur=None,
			type="TENTATIVE_FRAUDE",
			description="Incident borne non rattache",
			event_status="BLOCKED",
			device_name="bioattend-pi",
			details={"stage": "liveness"},
		)

		response = self.client.get(
			reverse("Employee:statistiques_utilisateur", kwargs={"utilisateur_id": target.pk}),
			{"tab": "problemes"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Incident borne non rattache")
		self.assertContains(response, "Echec rattache utilisateur")
		self.assertEqual(len(response.context["problem_alerts"]), 2)

	def test_alerte_list_filters_by_category(self):
		user = self._create_user("alert-user")
		self.client.force_login(user)

		Alerte.objects.create(
			utilisateur=user,
			type="UTILISATEUR_INCONNU",
			description="Utilisateur non reconnu",
		)
		Alerte.objects.create(
			utilisateur=user,
			type="TENTATIVE_FRAUDE",
			description="Liveness negatif",
		)

		response = self.client.get(reverse("Employee:alerte_list"), {"categorie": "UTILISATEUR_INCONNU"})

		self.assertEqual(response.status_code, 200)
		alertes = list(response.context["alertes"])
		self.assertEqual(len(alertes), 1)
		self.assertEqual(alertes[0].type, "UTILISATEUR_INCONNU")

	def test_alerte_list_delete_selected_removes_rows_from_db(self):
		user = self._create_user("alert-delete")
		self.client.force_login(user)

		pointage = Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			horodatage=timezone.now(),
			type="ENTREE",
			score_confiance=0.91,
		)
		alerte_a_masquer = Alerte.objects.create(
			utilisateur=user,
			pointage=pointage,
			type="UTILISATEUR_INCONNU",
			description="Test suppression cible",
		)
		alerte_visible = Alerte.objects.create(
			utilisateur=user,
			type="TENTATIVE_FRAUDE",
			description="Test conservation",
		)

		response = self.client.post(
			reverse("Employee:alerte_list"),
			{
				"action": "delete_selected",
				"selected_alert_ids": [str(alerte_a_masquer.pk)],
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Alerte.objects.filter(pk=alerte_a_masquer.pk).exists())
		self.assertTrue(Alerte.objects.filter(pk=alerte_visible.pk).exists())
		self.assertTrue(Pointage.objects.filter(pk=pointage.pk).exists())
		self.assertTrue(Utilisateur.objects.filter(pk=user.pk).exists())

		listing = self.client.get(reverse("Employee:alerte_list"))
		self.assertNotContains(listing, "Test suppression cible")
		self.assertContains(listing, "Test conservation")

	def test_alerte_list_delete_all_respects_current_filter(self):
		user = self._create_user("alert-delete-all")
		self.client.force_login(user)

		alerte_inconnue = Alerte.objects.create(
			utilisateur=user,
			type="UTILISATEUR_INCONNU",
			description="A supprimer",
		)
		alerte_fraude = Alerte.objects.create(
			utilisateur=user,
			type="TENTATIVE_FRAUDE",
			description="A conserver",
		)

		response = self.client.post(
			reverse("Employee:alerte_list") + "?categorie=UTILISATEUR_INCONNU",
			{"action": "delete_all"},
		)

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Alerte.objects.filter(pk=alerte_inconnue.pk).exists())
		self.assertTrue(Alerte.objects.filter(pk=alerte_fraude.pk).exists())

	def test_alerte_list_post_deletes_selected_alertes(self):
		user = self._create_user("alert-user-selected")
		self.client.force_login(user)

		alert1 = Alerte.objects.create(
			utilisateur=user,
			type="ECHEC_RECONNAISSANCE",
			description="Visage non detecte",
		)
		alert2 = Alerte.objects.create(
			utilisateur=user,
			type="TENTATIVE_FRAUDE",
			description="Photo detectee",
		)

		response = self.client.post(
			reverse("Employee:alerte_list"),
			{"delete_selected": "1", "selected_alertes": [str(alert1.id)]},
		)

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Alerte.objects.filter(pk=alert1.pk).exists())
		self.assertTrue(Alerte.objects.filter(pk=alert2.pk).exists())

	def test_alerte_list_post_deletes_all_alertes(self):
		user = self._create_user("alert-user-all")
		self.client.force_login(user)

		Alerte.objects.create(
			utilisateur=user,
			type="UTILISATEUR_INCONNU",
			description="Visage inconnu detecte",
		)
		Alerte.objects.create(
			utilisateur=user,
			type="ECHEC_RECONNAISSANCE",
			description="Visage non detecte",
		)

		response = self.client.post(reverse("Employee:alerte_list"), {"delete_all": "1"})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(Alerte.objects.count(), 0)

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
		self.assertIn("text/csv", response["Content-Type"])
		self.assertIn("charset=utf-8", response["Content-Type"])
		self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
		content = response.content.decode("utf-8-sig")
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
		self.assertIn("text/csv", response["Content-Type"])
		self.assertIn("charset=utf-8", response["Content-Type"])
		self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
		content = response.content.decode("utf-8-sig")
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

	def test_alerte_export_csv_returns_filtered_security_alerts(self):
		user = self._create_user("csv-alert-admin")
		self.client.force_login(user)

		Alerte.objects.create(
			utilisateur=None,
			type="UTILISATEUR_INCONNU",
			description="Visage inconnu en entree",
			device_name="borne-a",
		)
		Alerte.objects.create(
			utilisateur=None,
			type="TENTATIVE_FRAUDE",
			description="Photo detectee",
			device_name="borne-b",
		)

		response = self.client.get(
			reverse("Employee:alerte_export_csv"),
			{"categorie": "UTILISATEUR_INCONNU"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn("text/csv", response["Content-Type"])
		self.assertIn("charset=utf-8", response["Content-Type"])
		self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
		content = response.content.decode("utf-8-sig")
		self.assertIn("Date,Type,Concerne,Description", content)
		self.assertIn("Inconnu", content)
		self.assertIn("Visage inconnu en entree", content)
		self.assertNotIn("Photo detectee", content)

	def test_delete_notification_removes_security_history_entry(self):
		admin = self._create_user("notif-separate-admin")
		self.client.force_login(admin)

		alerte = Alerte.objects.create(
			utilisateur=None,
			type="UTILISATEUR_INCONNU",
			description="Incident conserve dans securite",
		)

		response = self.client.post(
			reverse("Employee:alerte_list"),
			{"action": "delete_selected", "selected_alert_ids": [str(alerte.pk)]},
		)
		self.assertEqual(response.status_code, 302)
		self.assertFalse(Alerte.objects.filter(pk=alerte.pk).exists())

		security_response = self.client.get(reverse("Employee:statistiques_problemes"))
		self.assertEqual(security_response.status_code, 200)
		self.assertNotContains(security_response, "Incident conserve dans securite")

	def test_security_export_csv_includes_problem_history(self):
		user = self._create_user("security-export-admin")
		self.client.force_login(user)

		Alerte.objects.create(
			utilisateur=None,
			type="TENTATIVE_FRAUDE",
			description="Incident export securite",
			masquee=True,
		)

		response = self.client.get(
			reverse("Employee:alerte_export_csv"),
			{"tab": "problemes", "problem_type": "TENTATIVE_FRAUDE"},
		)

		self.assertEqual(response.status_code, 200)
		content = response.content.decode("utf-8")
		self.assertIn("Incident export securite", content)
