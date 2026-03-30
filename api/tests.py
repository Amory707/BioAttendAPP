import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, RoleUtilisateur, Utilisateur
from alerts.models import Alerte
from attendance.models import Pointage


class FaceIdentifyApiTests(TestCase):
	def tearDown(self):
		# Nettoyage explicite demande: suppression de tout ajout en base.
		Alerte.objects.all().delete()
		Pointage.objects.all().delete()
		RoleUtilisateur.objects.all().delete()
		Utilisateur.objects.all().delete()
		Role.objects.all().delete()

	def _url(self):
		return reverse("api:face-identify")

	def _mock_queryset_chain(self, first_result=None, raise_on_filter=False):
		queryset = Mock()
		queryset.annotate.return_value = queryset
		queryset.order_by.return_value = queryset
		queryset.first.return_value = first_result

		if raise_on_filter:
			with patch("api.views.Utilisateur.objects.filter", side_effect=Exception("db error")):
				response = self.client.post(self._url(), {"embedding": [0.1] * 512}, content_type="application/json")
			return response

		with patch("api.views.Utilisateur.objects.filter", return_value=queryset):
			response = self.client.post(self._url(), {"embedding": [0.1] * 512}, content_type="application/json")
		return response

	def _embedding_from_face_file(self):
		image_path = Path("/workspaces/BioAttendAPP/api/visage test/louis-de-funes.jpeg")
		with image_path.open("rb") as image_file:
			content = image_file.read()

		# Derive un vecteur de 512 floats deterministe depuis le fichier image.
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
		response = self.client.post(self._url(), {}, content_type="application/json")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()["matched"], False)
		self.assertIn("embedding", response.json()["error"])

	def test_identify_rejects_non_list_embedding(self):
		response = self.client.post(
			self._url(),
			{"embedding": "not-a-list"},
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("liste", response.json()["error"])

	def test_identify_rejects_wrong_embedding_size(self):
		response = self.client.post(
			self._url(),
			{"embedding": [0.1] * 3},
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("512", response.json()["error"])

	def test_identify_rejects_non_numeric_values(self):
		payload = [0.2] * 511 + ["x"]
		response = self.client.post(
			self._url(),
			{"embedding": payload},
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertIn("nombres", response.json()["error"])

	def test_identify_returns_500_when_query_fails(self):
		response = self._mock_queryset_chain(raise_on_filter=True)

		self.assertEqual(response.status_code, 500)
		self.assertEqual(response.json()["matched"], False)

	def test_identify_returns_404_when_no_match(self):
		response = self._mock_queryset_chain(first_result=None)

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.json()["matched"], False)

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
			response = self.client.post(
				self._url(),
				{"embedding": embedding},
				content_type="application/json",
			)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload["matched"])
		self.assertEqual(payload["username"], "face-file-user")
