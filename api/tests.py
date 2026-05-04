import hashlib
import requests
import uuid

from datetime import datetime, time, timedelta

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, RoleUtilisateur, Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage
from schedule.services import get_schedule_settings


@override_settings(SECRET_KEY="test-api-secret")
class FaceIdentifyApiTests(TestCase):
	API_KEY = "test-api-secret"

	def tearDown(self):
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Utilisateur.objects.all().delete()
		Role.objects.all().delete()

	def _url(self):
		return reverse("api:face-identify")

	def _auth_headers(self, mode="bearer", key=None):
		api_key = self.API_KEY if key is None else key
		if mode == "x-api-key":
			return {"HTTP_X_API_KEY": api_key}
		return {"HTTP_AUTHORIZATION": f"Bearer {api_key}"}

	def _post(self, payload, auth_mode="bearer", key=None):
		headers = self._auth_headers(mode=auth_mode, key=key)
		return self.client.post(
			self._url(),
			payload,
			content_type="application/json",
			**headers,
		)

	def _mock_queryset_chain(self, first_result=None, raise_on_filter=False):
		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = first_result

		if raise_on_filter:
			with patch("api.views.Utilisateur.objects.filter", side_effect=Exception("db error")):
				response = self._post({"embedding": [0.1] * 512})
			return response

		with patch("api.views.Utilisateur.objects.filter", return_value=queryset):
			response = self._post({"embedding": [0.1] * 512})
		return response

	def _embedding_from_face_file(self):
		image_path = Path("/workspaces/BioAttendAPP/api/visage test/louis-de-funes.jpeg")
		with image_path.open("rb") as image_file:
			content = image_file.read()

		values = []
		counter = 0
		while len(values) < 512:
			digest = hashlib.sha256(content + str(counter).encode("utf-8")).digest()
			for byte in digest:
				values.append((byte / 127.5) - 1.0)
				if len(values) == 512:
					break
			counter += 1
		return values

	def test_identify_requires_embedding_field(self):
		response = self._post({})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()["matched"], False)
		self.assertIn("embedding", response.json()["error"])

	def test_identify_rejects_non_list_embedding(self):
		response = self._post(
			{"embedding": "not-a-list"},
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("liste", response.json()["error"])

	def test_identify_rejects_wrong_embedding_size(self):
		response = self._post(
			{"embedding": [0.1] * 3},
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("512", response.json()["error"])

	def test_identify_rejects_non_numeric_values(self):
		payload = [0.2] * 511 + ["x"]
		response = self._post(
			{"embedding": payload},
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("nombres", response.json()["error"])

	def test_identify_returns_500_when_query_fails(self):
		response = self._mock_queryset_chain(raise_on_filter=True)

		self.assertEqual(response.status_code, 500)
		self.assertEqual(response.json()["matched"], False)

	def test_identify_returns_403_when_fraud_detected(self):
		response = self._post(
			{"embedding": [0.1] * 512, "fraud_detected": True, "fraud_reason": "Photo imprimee detectee."},
		)

		self.assertEqual(response.status_code, 403)
		self.assertEqual(response.json()["matched"], False)
		self.assertEqual(Pointage.objects.filter(incident_type="TENTATIVE_FRAUDE").count(), 1)
		pointage = Pointage.objects.filter(incident_type="TENTATIVE_FRAUDE").first()
		self.assertIsNone(pointage.utilisateur)
		self.assertEqual(pointage.statut, "NON_VALIDE")
		self.assertEqual(pointage.origine, Pointage.ORIGINE_POINTEUSE)
		alerte = Alerte.objects.get(type="TENTATIVE_FRAUDE")
		self.assertEqual(alerte.pointage_id, pointage.id)
		self.assertIn("Photo imprimee detectee", alerte.description)

	def test_identify_test_mode_does_not_create_fraud_incident(self):
		response = self._post(
			{
				"embedding": [0.1] * 512,
				"fraud_detected": True,
				"fraud_reason": "Photo imprimee detectee.",
				"ingestion_mode": "test",
			},
		)

		self.assertEqual(response.status_code, 403)
		self.assertEqual(Pointage.objects.filter(incident_type="TENTATIVE_FRAUDE").count(), 0)
		self.assertEqual(Alerte.objects.filter(type="TENTATIVE_FRAUDE").count(), 0)

	def test_identify_returns_404_when_no_match(self):
		response = self._mock_queryset_chain(first_result=None)

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.json()["matched"], False)
		self.assertEqual(Pointage.objects.filter(incident_type="UTILISATEUR_INCONNU").count(), 1)
		pointage = Pointage.objects.filter(incident_type="UTILISATEUR_INCONNU").first()
		self.assertIsNotNone(pointage)
		self.assertEqual(pointage.statut, "NON_VALIDE")
		alerte = Alerte.objects.get(type="UTILISATEUR_INCONNU")
		self.assertEqual(alerte.pointage_id, pointage.id)

	def test_identify_test_mode_does_not_create_incident_when_no_match(self):
		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = None

		with patch("api.views.Utilisateur.objects.filter", return_value=queryset):
			response = self._post({"embedding": [0.1] * 512, "ingestion_mode": "test"})

		self.assertEqual(response.status_code, 404)
		self.assertEqual(Pointage.objects.filter(incident_type="UTILISATEUR_INCONNU").count(), 0)
		self.assertEqual(Alerte.objects.filter(type="UTILISATEUR_INCONNU").count(), 0)

	@override_settings(FACE_MATCH_THRESHOLD=0.5)
	def test_identify_returns_404_when_distance_above_threshold(self):
		far_match = SimpleNamespace(
			id=uuid.uuid4(),
			username="far-user",
			distance=0.9,
			get_full_name=lambda: "Far User",
		)
		response = self._mock_queryset_chain(first_result=far_match)

		self.assertEqual(response.status_code, 404)
		self.assertIn("Aucun visage", response.json()["error"])
		self.assertEqual(Pointage.objects.filter(incident_type="ECHEC_RECONNAISSANCE").count(), 1)
		self.assertEqual(Pointage.objects.filter(incident_type="UTILISATEUR_INCONNU").count(), 0)
		pointage = Pointage.objects.filter(incident_type="ECHEC_RECONNAISSANCE").first()
		self.assertIsNone(pointage.utilisateur)
		self.assertEqual(pointage.details["candidate_username"], "far-user")
		alerte = Alerte.objects.get(type="ECHEC_RECONNAISSANCE")
		self.assertEqual(alerte.pointage_id, pointage.id)

	@override_settings(FACE_MATCH_THRESHOLD=0.5)
	def test_identify_returns_404_when_distance_above_threshold_with_real_user_object(self):
		user = Utilisateur.objects.create_user(
			username="far-user-real",
			email="far-real@example.com",
			password="pass-123",
			first_name="Far",
			last_name="Real",
		)
		user.distance = 0.9

		response = self._mock_queryset_chain(first_result=user)

		self.assertEqual(response.status_code, 404)
		self.assertIn("Aucun visage", response.json()["error"])
		self.assertEqual(Pointage.objects.filter(incident_type="ECHEC_RECONNAISSANCE").count(), 1)
		pointage = Pointage.objects.filter(incident_type="ECHEC_RECONNAISSANCE").first()
		self.assertIsNone(pointage.utilisateur)
		self.assertEqual(pointage.details["candidate_username"], "far-user-real")
		alerte = Alerte.objects.get(type="ECHEC_RECONNAISSANCE")
		self.assertEqual(alerte.pointage_id, pointage.id)

	@override_settings(FACE_MATCH_THRESHOLD=0.5)
	def test_identify_returns_200_when_match_found(self):
		user = Utilisateur.objects.create_user(
			username="matched-user",
			email="matched@example.com",
			password="pass-123",
			first_name="Jean",
			last_name="Dupont",
		)
		user.distance = 0.12

		response = self._mock_queryset_chain(first_result=user)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload["matched"])
		self.assertEqual(payload["username"], "matched-user")
		self.assertEqual(payload["full_name"], "Jean Dupont")
		self.assertEqual(payload["distance"], 0.12)

	def test_identify_test_mode_matches_without_creating_pointage(self):
		user = Utilisateur.objects.create_user(
			username="test-mode-user",
			email="testmode@example.com",
			password="pass-123",
		)
		user.distance = 0.11

		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = user

		with patch("api.views.Utilisateur.objects.filter", return_value=queryset):
			response = self._post({"embedding": [0.1] * 512, "ingestion_mode": "test"})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload["matched"])
		self.assertEqual(payload["ingestion_mode"], "test")
		self.assertIsNone(payload["pointage_id"])
		self.assertIsNone(payload["pointage_type"])
		self.assertEqual(Pointage.objects.filter(utilisateur=user).count(), 0)

	def test_identify_rejects_invalid_ingestion_mode(self):
		response = self._post({"embedding": [0.1] * 512, "ingestion_mode": "staging"})

		self.assertEqual(response.status_code, 400)
		self.assertIn("ingestion_mode", response.json()["error"])

	def test_identify_returns_401_without_api_key(self):
		response = self.client.post(
			self._url(),
			{"embedding": [0.1] * 512},
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 401)
		self.assertFalse(response.json()["matched"])

	def test_identify_returns_401_with_invalid_api_key(self):
		response = self._post({"embedding": [0.1] * 512}, key="wrong-key")

		self.assertEqual(response.status_code, 401)
		self.assertFalse(response.json()["matched"])

	def test_identify_accepts_x_api_key_header(self):
		response = self._post(
			{"embedding": [0.1] * 3},
			auth_mode="x-api-key",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("512", response.json()["error"])

	@override_settings(FACE_MATCH_THRESHOLD=0.7)
	def test_identify_with_face_file_embedding_returns_200(self):
		image_path = Path("/workspaces/BioAttendAPP/api/visage test/louis-de-funes.jpeg")
		self.assertTrue(image_path.exists())

		embedding = self._embedding_from_face_file()
		user = Utilisateur.objects.create_user(
			username="face-file-user",
			email="face@example.com",
			password="pass-123",
			first_name="Louis",
			last_name="Funes",
		)
		user.distance = 0.33

		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = user

		with patch("api.views.Utilisateur.objects.filter", return_value=queryset):
			response = self._post({"embedding": embedding})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload["matched"])
		self.assertEqual(payload["username"], "face-file-user")

	def test_identify_creates_pointeuse_pointages_with_automatic_toggle(self):
		user = Utilisateur.objects.create_user(
			username="toggle-user",
			email="toggle@example.com",
			password="pass-123",
		)
		user.distance = 0.08

		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = user

		with patch("api.views.Utilisateur.objects.filter", return_value=queryset):
			first_response = self._post({"embedding": [0.2] * 512})
			second_response = self._post({"embedding": [0.2] * 512})

		self.assertEqual(first_response.status_code, 200)
		self.assertEqual(second_response.status_code, 200)
		self.assertEqual(first_response.json()["pointage_type"], "ENTREE")
		self.assertEqual(second_response.json()["pointage_type"], "SORTIE")

		pointage_types = list(
			Pointage.objects.filter(
				utilisateur=user,
				origine=Pointage.ORIGINE_POINTEUSE,
			)
			.order_by("horodatage", "id")
			.values_list("type", flat=True)
		)
		self.assertEqual(pointage_types, ["ENTREE", "SORTIE"])

	def test_identify_returns_late_feedback_for_entry_pointage(self):
		settings_obj = get_schedule_settings()
		settings_obj.is_enabled = True
		settings_obj.arrival_window_end = time(10, 0)
		settings_obj.save(update_fields=["is_enabled", "arrival_window_end", "updated_at"])

		user = Utilisateur.objects.create_user(
			username="late-entry-user",
			email="late-entry@example.com",
			password="pass-123",
		)
		user.distance = 0.05
		entry_time = timezone.make_aware(datetime.combine(timezone.localdate(), time(10, 30)))

		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = user

		with (
			patch("api.views.Utilisateur.objects.filter", return_value=queryset),
			patch("api.views.timezone.now", return_value=entry_time),
		):
			response = self._post({"embedding": [0.2] * 512})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["pointage_type"], "ENTREE")
		self.assertIn("RETARD", payload["schedule_flags"])
		self.assertTrue(any("Retard de 0h30" in message for message in payload["schedule_feedback"]))

	def test_identify_returns_work_duration_short_day_and_early_departure_for_exit_pointage(self):
		settings_obj = get_schedule_settings()
		settings_obj.is_enabled = True
		settings_obj.departure_window_start = time(16, 0)
		settings_obj.required_daily_minutes = 8 * 60
		settings_obj.save(update_fields=["is_enabled", "departure_window_start", "required_daily_minutes", "updated_at"])

		user = Utilisateur.objects.create_user(
			username="early-exit-user",
			email="early-exit@example.com",
			password="pass-123",
		)
		user.distance = 0.05
		target_day = timezone.localdate()
		entry_time = timezone.make_aware(datetime.combine(target_day, time(10, 30)))
		exit_time = entry_time + timedelta(hours=4, minutes=30)
		Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			type="ENTREE",
			horodatage=entry_time,
			score_confiance=0.9,
			origine=Pointage.ORIGINE_POINTEUSE,
		)

		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = user

		with (
			patch("api.views.Utilisateur.objects.filter", return_value=queryset),
			patch("api.views.timezone.now", return_value=exit_time),
		):
			response = self._post({"embedding": [0.2] * 512})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["pointage_type"], "SORTIE")
		self.assertEqual(payload["worked_duration_display"], "4h30")
		self.assertIn("DEPART_ANTICIPE", payload["schedule_flags"])
		self.assertIn("JOURNEE_COURTE", payload["schedule_flags"])
		self.assertTrue(any("Départ anticipé" in message for message in payload["schedule_feedback"]))
		self.assertTrue(any("Travail effectif réduit" in message for message in payload["schedule_feedback"]))

	def test_identify_toggle_ignores_manual_pointage_history(self):
		user = Utilisateur.objects.create_user(
			username="manual-history-user",
			email="manual-history@example.com",
			password="pass-123",
		)
		user.distance = 0.05

		Pointage.objects.create(
			utilisateur=user,
			statut="VALIDE",
			type="SORTIE",
			horodatage=timezone.now(),
			score_confiance=0.9,
			origine=Pointage.ORIGINE_MANUEL,
		)

		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = user

		with patch("api.views.Utilisateur.objects.filter", return_value=queryset):
			response = self._post({"embedding": [0.3] * 512})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["pointage_type"], "ENTREE")


@override_settings(SECRET_KEY="test-api-secret")
class AbsenceAlertApiTests(TestCase):
	API_KEY = "test-api-secret"

	def tearDown(self):
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Role.objects.all().delete()
		Utilisateur.objects.all().delete()

	def _url(self):
		return reverse("api:absence-alert")

	def _auth_headers(self, mode="bearer", key=None):
		api_key = self.API_KEY if key is None else key
		if mode == "x-api-key":
			return {"HTTP_X_API_KEY": api_key}
		return {"HTTP_AUTHORIZATION": f"Bearer {api_key}"}

	def _get(self, params=None, auth_mode="bearer", key=None):
		headers = self._auth_headers(mode=auth_mode, key=key)
		return self.client.get(
			self._url(),
			params or {},
			content_type="application/json",
			**headers,
		)

	def _post(self, payload, auth_mode="bearer", key=None):
		headers = self._auth_headers(mode=auth_mode, key=key)
		return self.client.post(
			self._url(),
			payload,
			content_type="application/json",
			**headers,
		)

	def test_absence_alert_requires_authentication(self):
		response = self.client.get(
			self._url(),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 401)
		self.assertFalse(response.json()["alert_sent"])

	def test_absence_alert_returns_empty_when_no_absences(self):
		response = self._get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["absences"], [])

	@override_settings(BREVO_API_KEY='test-brevo-key', BREVO_SENDER_EMAIL='no-reply@example.com', BREVO_SENDER_NAME='BioAttend Test')
	@patch('schedule.services.requests.post')
	def test_absence_alert_sends_email_after_day_finished(self, mock_post):
		admin_role = Role.objects.create(nom='admin')
		admin_user = Utilisateur.objects.create_user(
			username='admin-user',
			email='admin@example.com',
			password='pass-123',
		)
		RoleUtilisateur.objects.create(role=admin_role, utilisateur=admin_user)

		employee = Utilisateur.objects.create_user(
			username='employee-user',
			email='employee@example.com',
			password='pass-123',
		)

		mock_response = mock_post.return_value
		mock_response.status_code = 201
		mock_response.raise_for_status.return_value = None

		target_day = timezone.localdate()
		now_after_day = timezone.make_aware(datetime.combine(target_day, time(18, 30)))

		with patch('schedule.services.timezone.now', return_value=now_after_day):
			response = self._get({"date": target_day.strftime('%Y-%m-%d')})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["checked"], 1)
		self.assertEqual(len(payload["absences"]), 1)
		self.assertTrue(payload["absences"][0]["alert_created"])
		self.assertTrue(payload["absences"][0]["email_sent"])
		self.assertTrue(mock_post.called)

	@override_settings(BREVO_API_KEY='test-brevo-key', BREVO_SENDER_EMAIL='no-reply@example.com', BREVO_SENDER_NAME='BioAttend Test')
	@patch('schedule.services.requests.post')
	def test_absence_alert_returns_500_when_email_send_fails(self, mock_post):
		admin_role = Role.objects.create(nom='admin')
		admin_user = Utilisateur.objects.create_user(
			username='admin-user',
			email='admin@example.com',
			password='pass-123',
		)
		RoleUtilisateur.objects.create(role=admin_role, utilisateur=admin_user)

		employee = Utilisateur.objects.create_user(
			username='employee-user',
			email='employee@example.com',
			password='pass-123',
		)

		mock_post.side_effect = requests.RequestException('Brevo unreachable')

		target_day = timezone.localdate()
		now_after_day = timezone.make_aware(datetime.combine(target_day, time(18, 30)))

		with patch('schedule.services.timezone.now', return_value=now_after_day):
			response = self._get({"date": target_day.strftime('%Y-%m-%d')})

		self.assertEqual(response.status_code, 500)
		payload = response.json()
		self.assertFalse(payload["alert_sent"])
		self.assertIn('Brevo', payload["error"])

	def test_absence_alert_does_not_send_before_day_finished(self):
		employee = Utilisateur.objects.create_user(
			username='employee-user',
			email='employee@example.com',
			password='pass-123',
		)

		target_day = timezone.localdate()
		now_before_end = timezone.make_aware(datetime.combine(target_day, time(17, 0)))

		with patch('schedule.services.timezone.now', return_value=now_before_end):
			response = self._get({"date": target_day.strftime('%Y-%m-%d')})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["absences"], [])


@override_settings(SECRET_KEY="test-api-secret")
class FrontEventApiTests(TestCase):
	API_KEY = "test-api-secret"

	def tearDown(self):
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()

	def _url(self):
		return reverse("api:front-events")

	def _post(self, payload, key=None):
		api_key = self.API_KEY if key is None else key
		return self.client.post(
			self._url(),
			payload,
			content_type="application/json",
			HTTP_AUTHORIZATION=f"Bearer {api_key}",
		)

	def test_front_event_requires_authentication(self):
		response = self.client.post(
			self._url(),
			{},
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 401)
		self.assertFalse(response.json()["logged"])

	def test_front_event_rejects_invalid_event_type(self):
		response = self._post(
			{
				"event_type": "bad-type",
				"status": "blocked",
				"message": "Tentative invalide",
				"device_name": "bioattend-pi",
				"details": {},
			}
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("event_type", response.json()["error"])

	def test_front_event_rejects_non_object_details(self):
		response = self._post(
			{
				"event_type": "spoof_attempt",
				"status": "blocked",
				"message": "Tentative d'usurpation détectée",
				"device_name": "bioattend-pi",
				"details": ["invalid"],
			}
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("details", response.json()["error"])

	def test_front_event_creates_alert_with_device_context(self):
		response = self._post(
			{
				"event_type": "spoof_attempt",
				"status": "blocked",
				"message": "Tentative d'usurpation détectée par la liveness",
				"device_name": "bioattend-pi",
				"details": {
					"stage": "liveness",
					"liveness_score": 0.12,
				},
			}
		)

		self.assertEqual(response.status_code, 201)
		payload = response.json()
		self.assertTrue(payload["logged"])
		self.assertEqual(payload["event_type"], "spoof_attempt")
		self.assertEqual(payload["status"], "blocked")

		pointage = Pointage.objects.get(id=payload["event_id"])
		self.assertEqual(pointage.incident_type, "TENTATIVE_FRAUDE")
		self.assertEqual(pointage.device_name, "bioattend-pi")
		self.assertEqual(pointage.details["status"], "BLOCKED")
		self.assertEqual(pointage.details["stage"], "liveness")
		self.assertEqual(pointage.details["liveness_score"], 0.12)
		self.assertEqual(pointage.statut, "NON_VALIDE")
		self.assertEqual(pointage.origine, Pointage.ORIGINE_POINTEUSE)

		alerte = Alerte.objects.get(pointage=pointage)
		self.assertEqual(alerte.type, "TENTATIVE_FRAUDE")
		self.assertEqual(alerte.device_name, "bioattend-pi")
		self.assertEqual(alerte.event_status, "BLOCKED")
		self.assertIn("liveness", alerte.details["stage"])
