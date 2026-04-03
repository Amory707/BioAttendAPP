from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, RoleUtilisateur, Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage


class DashboardAppTests(TestCase):
	def tearDown(self):
		# Nettoyage explicite demande: suppression de tout ajout en base.
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
