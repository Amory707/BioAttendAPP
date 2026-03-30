from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse

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

	def test_logout_view_logs_out_and_redirects_to_login(self):
		user = self._create_user("logout-user")
		self.client.force_login(user)

		response = self.client.get(reverse("dashboard:logout"))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("login"))
		self.assertNotIn("_auth_user_id", self.client.session)
