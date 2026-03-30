from importlib import import_module

from django.conf import settings
from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, RoleUtilisateur, Utilisateur


class AccountsAppTests(TestCase):
	def tearDown(self):
		# Nettoyage explicite demande: suppression de tout ajout en base.
		Session.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Utilisateur.objects.all().delete()
		Role.objects.all().delete()

	def _create_user(self, username, password="test-pass-123", **extra):
		defaults = {
			"email": f"{username}@example.com",
			"first_name": "John",
			"last_name": "Doe",
			"password": password,
		}
		defaults.update(extra)
		return Utilisateur.objects.create_user(username=username, **defaults)

	def _create_role(self, nom):
		return Role.objects.create(nom=nom)

	def _create_authenticated_session_for_user(self, user):
		session_engine = import_module(settings.SESSION_ENGINE)
		store = session_engine.SessionStore()
		store["_auth_user_id"] = str(user.pk)
		store["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
		store["_auth_user_hash"] = user.get_session_auth_hash()
		store.create()
		return store.session_key

	def test_custom_login_rejects_employe_role(self):
		employe_role = self._create_role("employé")
		user = self._create_user("agent")
		RoleUtilisateur.objects.create(role=employe_role, utilisateur=user)

		response = self.client.post(
			reverse("accounts:login"),
			{"username": "agent", "password": "test-pass-123"},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		messages = [m.message for m in get_messages(response.wsgi_request)]
		self.assertTrue(any("Accès refusé" in message for message in messages))

	def test_custom_login_accepts_non_employe_user(self):
		self._create_role("admin")
		user = self._create_user("manager")

		response = self.client.post(
			reverse("accounts:login"),
			{"username": "manager", "password": "test-pass-123"},
		)

		self.assertEqual(response.status_code, 302)
		self.assertTrue(response.url)
		self.assertTrue("_auth_user_id" in self.client.session)

	def test_settings_view_requires_authentication(self):
		response = self.client.get(reverse("accounts:settings"))
		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse("accounts:login"), response.url)

	def test_settings_view_returns_current_session_key(self):
		user = self._create_user("settings-user")
		self.client.force_login(user)

		response = self.client.get(reverse("accounts:settings"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.context["current_session_key"],
			self.client.session.session_key,
		)

	def test_logout_all_sessions_get_redirects_to_settings(self):
		user = self._create_user("logout-get")
		self.client.force_login(user)

		response = self.client.get(reverse("accounts:logout_all_sessions"))

		self.assertEqual(response.status_code, 302)
		self.assertRedirects(response, reverse("accounts:settings"))

	def test_logout_all_sessions_post_keeps_current_session_when_all_not_set(self):
		user = self._create_user("logout-others")
		self.client.force_login(user)
		current_session_key = self.client.session.session_key
		extra_session_key = self._create_authenticated_session_for_user(user)

		response = self.client.post(reverse("accounts:logout_all_sessions"), {})

		self.assertEqual(response.status_code, 302)
		self.assertRedirects(response, reverse("accounts:settings"))
		self.assertTrue(Session.objects.filter(session_key=current_session_key).exists())
		self.assertFalse(Session.objects.filter(session_key=extra_session_key).exists())

	def test_logout_all_sessions_post_all_logs_out_user(self):
		user = self._create_user("logout-all")
		self.client.force_login(user)
		current_session_key = self.client.session.session_key
		extra_session_key = self._create_authenticated_session_for_user(user)

		response = self.client.post(
			reverse("accounts:logout_all_sessions"),
			{"all": "1"},
		)

		self.assertEqual(response.status_code, 302)
		self.assertRedirects(response, reverse("accounts:login"))
		self.assertFalse(Session.objects.filter(session_key=current_session_key).exists())
		self.assertFalse(Session.objects.filter(session_key=extra_session_key).exists())
		self.assertNotIn("_auth_user_id", self.client.session)

	def test_role_utilisateur_acces_total_sets_staff_and_permissions(self):
		user = self._create_user("staffable")
		acces_total = self._create_role("acces_total")

		RoleUtilisateur.objects.create(role=acces_total, utilisateur=user)
		user.refresh_from_db()

		self.assertTrue(user.is_staff)
		self.assertGreater(user.user_permissions.count(), 0)

	def test_utilisateur_role_properties(self):
		user = self._create_user("role-user")
		role_employe = self._create_role("employé")
		role_admin = self._create_role("admin")
		role_total = self._create_role("acces_total")
		RoleUtilisateur.objects.create(role=role_employe, utilisateur=user)
		RoleUtilisateur.objects.create(role=role_admin, utilisateur=user)
		RoleUtilisateur.objects.create(role=role_total, utilisateur=user)

		self.assertTrue(user.is_employe)
		self.assertTrue(user.is_acces_total)
		self.assertTrue(user.is_admindjango)
