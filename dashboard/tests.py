from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.access import ACTIVE_SPACE_SESSION_KEY, EMPLOYEE_SPACE
from accounts.models import Role, RoleUtilisateur, Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage


class DashboardAppTests(TestCase):
	def tearDown(self):
		Session.objects.all().delete()
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Utilisateur.objects.all().delete()
		Role.objects.all().delete()

	def _create_user(self, username, is_superuser=False):
		return Utilisateur.objects.create_user(
			username=username,
			email=f"{username}@example.com",
			password="test-pass-123",
			first_name="John",
			last_name="Doe",
			is_superuser=is_superuser,
			is_staff=is_superuser,
		)

	def _assign_role(self, user, role_name):
		role, _ = Role.objects.get_or_create(nom=role_name)
		RoleUtilisateur.objects.get_or_create(utilisateur=user, role=role)

	def test_dashboard_requires_authentication(self):
		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse("login"), response.url)

	def test_dashboard_allows_user_with_admin_role(self):
		user = self._create_user("admin-user")
		self._assign_role(user, "admin")
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["user"].pk, user.pk)
		self.assertContains(response, "Portail employé")

	def test_dashboard_shows_security_navigation_link(self):
		admin = self._create_user("admin-security-link")
		self._assign_role(admin, "admin")
		self.client.force_login(admin)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Incidents sécurité")
		self.assertContains(response, reverse("Employee:statistiques_problemes"))

	def test_dashboard_uses_real_metrics_in_context(self):
		admin = self._create_user("admin-metrics")
		employee_one = self._create_user("employee-one",)
		employee_two = self._create_user("employee-two")
		employee_one.first_name = "Lina"
		employee_one.last_name = "Ops"
		employee_one.save(update_fields=["first_name", "last_name"])
		self._assign_role(admin, "admin")
		self._assign_role(employee_one, "employé")
		self._assign_role(employee_two, "employé")
		self.client.force_login(admin)

		Pointage.objects.create(
			utilisateur=employee_one,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.91,
		)
		Pointage.objects.create(
			utilisateur=None,
			statut="NON_VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.0,
			origine=Pointage.ORIGINE_POINTEUSE,
			incident_type="UTILISATEUR_INCONNU",
		)
		Pointage.objects.create(
			utilisateur=employee_two,
			statut="NON_VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.18,
			origine=Pointage.ORIGINE_POINTEUSE,
			incident_type="ECHEC_RECONNAISSANCE",
		)
		Pointage.objects.create(
			utilisateur=None,
			statut="NON_VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.0,
			origine=Pointage.ORIGINE_POINTEUSE,
			incident_type="TENTATIVE_FRAUDE",
		)

		Alerte.objects.create(utilisateur=employee_one, type="RETARD", description="Retard détecté", statut="NOUVELLE")
		Alerte.objects.create(utilisateur=employee_one, type="DEPART_ANTICIPE", description="Départ anticipé détecté", statut="NOUVELLE")
		Alerte.objects.create(utilisateur=employee_one, type="JOURNEE_COURTE", description="Journée courte détectée", statut="NOUVELLE")

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["total_employees"], 2)
		self.assertEqual(response.context["today_present_count"], 1)
		self.assertEqual(response.context["today_absent_count"], 1)
		self.assertEqual(response.context["today_late_count"], 1)
		self.assertEqual(response.context["today_early_departure_count"], 1)
		self.assertEqual(response.context["today_short_day_count"], 1)
		self.assertEqual(response.context["not_recognized_today"], 3)
		self.assertEqual(len(response.context["weekly_stats"]), 7)
		self.assertContains(response, "Lina Ops")

	def test_dashboard_counts_non_admin_user_without_role(self):
		admin = self._create_user("admin-no-role")
		worker = self._create_user("worker-no-role")
		worker.first_name = "Noa"
		worker.last_name = "Field"
		worker.save(update_fields=["first_name", "last_name"])
		self._assign_role(admin, "admin")
		self.client.force_login(admin)

		Pointage.objects.create(
			utilisateur=worker,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.77,
		)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["total_employees"], 1)
		self.assertEqual(response.context["today_present_count"], 1)
		self.assertContains(response, "Noa Field")

	def test_dashboard_allows_user_with_acces_total_role(self):
		user = self._create_user("total-user")
		self._assign_role(user, "acces_total")
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)

	def test_dashboard_allows_bioattend_superuser_without_roles(self):
		user = self._create_user("bioattend", is_superuser=True)
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 200)

	def test_dashboard_denies_non_platform_admin_and_logs_out(self):
		user = self._create_user("employe-user")
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"), follow=True)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.redirect_chain[-1][0], reverse("login"))
		messages = [m.message for m in get_messages(response.wsgi_request)]
		self.assertTrue(any("Accès refusé" in message for message in messages))
		self.assertNotIn("_auth_user_id", self.client.session)

	def test_dashboard_redirects_employee_to_employee_home(self):
		user = self._create_user("employee-home")
		self._assign_role(user, "employé")
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:index"))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("dashboard:employee_home"))

	def test_switch_space_allows_admin_user_to_open_employee_space(self):
		user = self._create_user("hybrid-space")
		self._assign_role(user, "admin")
		self.client.force_login(user)
		admin_response = self.client.get(reverse("dashboard:index"))

		self.assertContains(admin_response, "Portail employé")

		response = self.client.get(reverse("dashboard:switch_space", args=[EMPLOYEE_SPACE]))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("dashboard:employee_home"))
		self.assertEqual(self.client.session.get(ACTIVE_SPACE_SESSION_KEY), EMPLOYEE_SPACE)

	def test_employee_home_allows_admin_user_when_employee_space_is_selected(self):
		user = self._create_user("hybrid-employee-home")
		self._assign_role(user, "admin")
		self.client.force_login(user)
		session = self.client.session
		session[ACTIVE_SPACE_SESSION_KEY] = EMPLOYEE_SPACE
		session.save()

		response = self.client.get(reverse("dashboard:employee_home"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Retour au portail gérance")

	def test_employee_home_shows_only_current_user_data(self):
		employee = self._create_user("employee-own")
		other = self._create_user("employee-other")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.9,
		)
		Pointage.objects.create(
			utilisateur=other,
			statut="VALIDE",
			type="SORTIE",
			horodatage=timezone.now(),
			score_confiance=0.8,
		)
		Alerte.objects.create(
			utilisateur=employee,
			type="RETARD",
			description="Retard personnel",
			statut="NOUVELLE",
		)
		Alerte.objects.create(
			utilisateur=other,
			type="ABSENCE",
			description="Absence autre utilisateur",
			statut="NOUVELLE",
		)

		response = self.client.get(reverse("dashboard:employee_home"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["total_pointages"], 1)
		self.assertEqual(response.context["pointages_valides"], 1)
		self.assertEqual(response.context["alertes_non_traitees"], 1)
		self.assertEqual(list(response.context["recent_pointages"])[0].utilisateur_id, employee.id)
		self.assertEqual(list(response.context["recent_alertes"])[0].utilisateur_id, employee.id)

	def test_employee_home_shows_punctuality_and_effective_work_time(self):
		employee = self._create_user("employee-punctuality")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		now = timezone.now().replace(hour=10, minute=30, second=0, microsecond=0)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now,
			score_confiance=0.96,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=15, minute=0),
			score_confiance=0.94,
		)

		response = self.client.get(reverse("dashboard:employee_home"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Départs anticipés")
		self.assertContains(response, "Retard détecté")
		self.assertContains(response, "4h30")

	def test_employee_home_computes_worked_time_from_valid_entry_exit_pairs(self):
		employee = self._create_user("employee-worktime")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now,
			score_confiance=0.96,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=12, minute=30),
			score_confiance=0.94,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now.replace(hour=13, minute=30),
			score_confiance=0.93,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=17, minute=0),
			score_confiance=0.91,
		)

		response = self.client.get(reverse("dashboard:employee_home"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["worked_time_today"], "8h00")
		self.assertContains(response, "8h00")

	def test_employee_pointages_filters_current_user_only(self):
		employee = self._create_user("employee-pointages")
		other = self._create_user("employee-other-pointages")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.95,
		)
		Pointage.objects.create(
			utilisateur=other,
			statut="VALIDE",
			type="ENTREE",
			horodatage=timezone.now(),
			score_confiance=0.82,
		)

		response = self.client.get(reverse("dashboard:employee_pointages"), {"type": "ENTREE"})

		self.assertEqual(response.status_code, 200)
		pointages = list(response.context["pointages"])
		self.assertEqual(len(pointages), 1)
		self.assertEqual(pointages[0].utilisateur_id, employee.id)

	def test_employee_prestations_exposes_daily_work_history(self):
		employee = self._create_user("employee-daily-history")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now,
			score_confiance=0.95,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=16, minute=45),
			score_confiance=0.93,
		)

		response = self.client.get(reverse("dashboard:employee_prestations"))

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["daily_work_history"])
		self.assertEqual(response.context["daily_work_history"][0]["duration_display"], "8h45")
		self.assertContains(response, "Historique des heures prestées")

	def test_employee_navigation_shows_prestations_tab(self):
		employee = self._create_user("employee-prestations-nav")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		response = self.client.get(reverse("dashboard:employee_home"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Mes prestations")
		self.assertContains(response, reverse("dashboard:employee_prestations"))

	def test_employee_prestations_page_exposes_chart_data(self):
		employee = self._create_user("employee-prestations-page")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now,
			score_confiance=0.98,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=17, minute=30),
			score_confiance=0.96,
		)

		response = self.client.get(reverse("dashboard:employee_prestations"))

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["daily_work_history"])
		self.assertIn("work_hours_chart_json", response.context)
		self.assertContains(response, "Graphique des heures prestées")
		self.assertContains(response, "workHoursChart")

	def test_employee_work_hours_csv_download(self):
		employee = self._create_user("employee-export-hours")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		now = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now,
			score_confiance=0.98,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=18, minute=15),
			score_confiance=0.97,
		)

		response = self.client.get(reverse("dashboard:employee_work_hours_csv"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
		self.assertIn("heures_prestées", response["Content-Disposition"])
		self.assertIn("9h15", response.content.decode("utf-8"))

	def test_employee_navigation_places_prestations_before_pointages(self):
		employee = self._create_user("employee-nav-order")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		response = self.client.get(reverse("dashboard:employee_home"))

		self.assertEqual(response.status_code, 200)
		content = response.content.decode("utf-8")
		self.assertTrue(content.find("Mes prestations") < content.find("Mes pointages"))

	def test_employee_prestations_uses_week_hours_and_exportable_graph(self):
		employee = self._create_user("employee-week-hours")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		now = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="ENTREE",
			horodatage=now,
			score_confiance=0.95,
		)
		Pointage.objects.create(
			utilisateur=employee,
			statut="VALIDE",
			type="SORTIE",
			horodatage=now.replace(hour=16, minute=0),
			score_confiance=0.94,
		)

		response = self.client.get(reverse("dashboard:employee_prestations"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Cette semaine")
		self.assertContains(response, "Exporter le graphe")
		self.assertNotContains(response, "Moyenne / jour")

	def test_employee_pointages_hides_prestation_summary(self):
		employee = self._create_user("employee-no-summary-pointages")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		response = self.client.get(reverse("dashboard:employee_pointages"))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, "Historique des heures prestées")
		self.assertNotContains(response, "Temps cumulé")
		self.assertNotContains(response, "Moyenne")

	def test_employee_alertes_filters_current_user_only(self):
		employee = self._create_user("employee-alertes")
		other = self._create_user("employee-other-alertes")
		self._assign_role(employee, "employé")
		self.client.force_login(employee)

		Alerte.objects.create(
			utilisateur=employee,
			type="RETARD",
			description="Alerte visible",
			statut="NOUVELLE",
		)
		Alerte.objects.create(
			utilisateur=other,
			type="ABSENCE",
			description="Alerte masquée",
			statut="NOUVELLE",
		)

		response = self.client.get(reverse("dashboard:employee_alertes"), {"statut": "NOUVELLE"})

		self.assertEqual(response.status_code, 200)
		alertes = list(response.context["alertes"])
		self.assertEqual(len(alertes), 1)
		self.assertEqual(alertes[0].utilisateur_id, employee.id)

	def test_logout_view_logs_out_and_redirects_to_login(self):
		user = self._create_user("logout-user")
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:logout"))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("login"))
		self.assertNotIn("_auth_user_id", self.client.session)
