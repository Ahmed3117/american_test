from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.authentication import MultiDeviceJWTAuthentication, _maybe_update_device_last_used
from accounts.models import User, UserDevice


class DeleteAccountTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='student1',
			password='pass1234',
			name='Student One',
			user_type='student'
		)
		self.admin = User.objects.create_superuser(
			username='admin',
			password='adminpass',
			email='admin@example.com'
		)
		self.url = reverse('accounts:delete-account')

	def test_authenticated_student_can_delete_account(self):
		self.client.force_authenticate(user=self.user)
		response = self.client.delete(self.url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertFalse(User.objects.filter(username='student1').exists())

	def test_unauthenticated_request_is_rejected(self):
		response = self.client.delete(self.url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_admin_cannot_use_student_delete_endpoint(self):
		self.client.force_authenticate(user=self.admin)
		response = self.client.delete(self.url)
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertTrue(User.objects.filter(username='admin').exists())


@override_settings(DEVICE_LAST_USED_UPDATE_INTERVAL_SECONDS=300)
class DeviceLastUsedUpdateTests(TestCase):
	def setUp(self):
		cache.clear()
		self.factory = APIRequestFactory()
		self.user = User.objects.create_user(
			username='device-user',
			password='pass1234',
			name='Device User',
			user_type='student'
		)
		self.device = UserDevice.objects.create(
			user=self.user,
			device_token='device-token',
			device_id='device-id',
			device_name='Test Device',
			ip_address='127.0.0.1',
			is_active=True
		)

	def tearDown(self):
		cache.clear()

	def test_recent_device_activity_does_not_write(self):
		with CaptureQueriesContext(connection) as queries:
			updated = _maybe_update_device_last_used(self.device)

		update_queries = [
			query for query in queries.captured_queries
			if 'UPDATE' in query['sql'].upper()
		]
		self.assertFalse(updated)
		self.assertEqual(update_queries, [])

	def test_student_authentication_validates_device_without_recent_write(self):
		token = AccessToken.for_user(self.user)
		token['device_token'] = self.device.device_token
		request = self.factory.get('/plans/', HTTP_AUTHORIZATION=f'Bearer {token}')

		with CaptureQueriesContext(connection) as queries:
			authenticated_user, validated_token = MultiDeviceJWTAuthentication().authenticate(request)

		update_queries = [
			query for query in queries.captured_queries
			if 'UPDATE' in query['sql'].upper()
		]
		self.assertEqual(authenticated_user.id, self.user.id)
		self.assertEqual(validated_token['device_token'], self.device.device_token)
		self.assertEqual(update_queries, [])

	def test_stale_device_activity_writes_once_then_cache_suppresses_repeats(self):
		stale_time = timezone.now() - timedelta(minutes=10)
		UserDevice.objects.filter(pk=self.device.pk).update(last_used_at=stale_time)
		self.device.refresh_from_db()

		with CaptureQueriesContext(connection) as first_queries:
			first_updated = _maybe_update_device_last_used(self.device)

		first_updates = [
			query for query in first_queries.captured_queries
			if 'UPDATE' in query['sql'].upper()
		]
		self.assertTrue(first_updated)
		self.assertEqual(len(first_updates), 1)

		with CaptureQueriesContext(connection) as second_queries:
			second_updated = _maybe_update_device_last_used(self.device)

		second_updates = [
			query for query in second_queries.captured_queries
			if 'UPDATE' in query['sql'].upper()
		]
		self.assertFalse(second_updated)
		self.assertEqual(second_updates, [])
