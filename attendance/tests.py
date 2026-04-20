from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, RoleUtilisateur, Utilisateur

from alerts.models import Alerte

from attendance.models import Pointage

class AttendanceAppTests(TestCase):
	def tearDown(self):
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Utilisateur.objects.all().delete()
		Role.objects.all().delete()

	def _create_user(self, username="pointage-user"):
		return Utilisateur.objects.create_user(
			username=username,
			email=f"{username}@example.com",
			password="test-pass-123",
			first_name="Jean",
			last_name="Dupont",
		)

	def test_pointage_str_contains_user_type_and_timestamp(self):
		user = self._create_user("str-user")
		now = timezone.now()
		pointage = Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			horodatage=now,
			type="ENTREE",
			score_confiance=0.98,
		)

		rendered = str(pointage)

		self.assertIn("ENTREE", rendered)
		self.assertIn("str-user", rendered)
		self.assertIn(str(now.date()), rendered)

	def test_pointage_default_ordering_is_desc_by_horodatage(self):
		user = self._create_user("order-user")
		older = Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			horodatage=timezone.now() - timedelta(hours=2),
			type="ENTREE",
			score_confiance=0.83,
		)
		newer = Pointage.objects.create(
			utilisateur=user,
			statut="NON_VALIDE",
			horodatage=timezone.now(),
			type="SORTIE",
			score_confiance=0.52,
		)

		ordered = list(Pointage.objects.all())

		self.assertEqual(ordered[0], newer)
		self.assertEqual(ordered[1], older)

	def test_pointage_full_clean_rejects_invalid_type_choice(self):
		user = self._create_user("invalid-type")
		pointage = Pointage(
			utilisateur=user,
			statut="VALIDE",
			horodatage=timezone.now(),
			type="PAUSE",
			score_confiance=0.7,
		)

		with self.assertRaises(ValidationError):
			pointage.full_clean()

	def test_pointage_full_clean_rejects_invalid_status_choice(self):
		user = self._create_user("invalid-status")
		pointage = Pointage(
			utilisateur=user,
			statut="EN_ATTENTE",
			horodatage=timezone.now(),
			type="ENTREE",
			score_confiance=0.7,
		)

		with self.assertRaises(ValidationError):
			pointage.full_clean()

	def test_deleting_utilisateur_cascades_to_pointages(self):
		user = self._create_user("cascade-user")
		Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			horodatage=timezone.now(),
			type="ENTREE",
			score_confiance=0.91,
		)

		user.delete()

		self.assertEqual(Pointage.objects.count(), 0)

	def test_pointage_can_be_linked_to_alert_then_deleted(self):
		user = self._create_user("alert-link-user")
		pointage = Pointage.objects.create(
			utilisateur=user,
			statut="NON_VALIDE",
			horodatage=timezone.now(),
			type="SORTIE",
			score_confiance=0.2,
		)
		alerte = Alerte.objects.create(
			utilisateur=user,
			pointage=pointage,
			type="ECHEC_RECONNAISSANCE",
			description="Echec de reconnaissance detecte.",
		)

		pointage.delete()
		alerte.refresh_from_db()

		self.assertIsNone(alerte.pointage)
