import unittest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from admission.models import User, Application

UserModel = get_user_model()

class UserAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email='test@example.com', password='testpassword')
        self.client.force_authenticate(user=self.user)

    def test_register_user(self):
        url = '/api/auth/register/'
        data = {'email': 'newuser@example.com', 'password': 'newpassword', 'role': 'student'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('email', response.data)
        self.assertIn('role', response.data)
        self.assertIn('created_at', response.data)

    def test_register_user_missing_email(self):
        url = '/api/auth/register/'
        data = {'password': 'newpassword', 'role': 'student'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_user_missing_password(self):
        url = '/api/auth/register/'
        data = {'email': 'newuser@example.com', 'role': 'student'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_user(self):
        url = '/api/auth/login/'
        data = {'email': 'test@example.com', 'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('refresh', response.data)
        self.assertIn('access', response.data)

    def test_login_user_invalid_credentials(self):
        url = '/api/auth/login/'
        data = {'email': 'test@example.com', 'password': 'wrongpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_user(self):
        url = '/api/auth/logout/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_create_application(self):
        url = '/api/applications/'
        data = {'details': 'Sample application details'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('status', response.data)
        self.assertIn('details', response.data)
        self.assertIn('submitted_at', response.data)

    def test_get_applications(self):
        url = '/api/applications/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_get_application_detail(self):
        application = Application.objects.create(user=self.user, details='Sample application details')
        url = f'/api/applications/{application.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['details'], 'Sample application details')

    def test_get_application_detail_not_found(self):
        url = '/api/applications/9999/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class HealthCheckTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_format(self):
        url = '/api/health/'
        response = self.client.get(url)
        expected_payload = {"status": "ok", "service": "Sage Backend v6"}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), expected_payload)
