from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, RoleUtilisateur, Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage


class CoreAppTests(TestCase):
	def tearDown(self):
		# Nettoyage explicite demande: suppression de tout ajout en base.
		Session.objects.all().delete()
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Utilisateur.objects.all().delete()
		Role.objects.all().delete()

	def _create_user(self, username="core-user"):
		return Utilisateur.objects.create_user(
			username=username,
			email=f"{username}@example.com",
			password="test-pass-123",
			first_name="Core",
			last_name="Tester",
		)

	def test_home_redirects_anonymous_user_to_login(self):
		response = self.client.get(reverse("core:home"))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("login"))

	def test_home_redirects_authenticated_user_to_dashboard(self):
		user = self._create_user()
		self.client.force_login(user)

		response = self.client.get(reverse("core:home"))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse("dashboard:index"))
