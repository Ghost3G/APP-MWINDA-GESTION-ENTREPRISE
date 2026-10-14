from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from users.security import authenticate_login

User = get_user_model()


class UsersDirectoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice',
            password='testpass123',
            email='alice@example.com',
            role='admin',
            direction='design',
        )

    def test_users_directory_requires_auth(self):
        response = self.client.get(reverse('users_list'))
        self.assertEqual(response.status_code, 302)

    def test_users_directory_renders_for_authenticated_user(self):
        self.client.login(username='alice', password='testpass123')
        response = self.client.get(reverse('users_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_user_from_users_directory(self):
        self.client.login(username='alice', password='testpass123')

        response = self.client.post(reverse('users_list'), {
            'username': 'bob',
            'email': 'bob@example.com',
            'first_name': 'Bob',
            'last_name': 'Mwinda',
            'password': 'SecretPass123!',
            'role': 'agent',
            'department': 'technique',
            'direction': 'metal_design',
        })

        self.assertRedirects(response, reverse('users_list'))
        created_user = User.objects.get(username='bob')
        self.assertEqual(created_user.email, 'bob@example.com')
        self.assertEqual(created_user.role, 'agent')
        self.assertEqual(created_user.direction, 'metal_design')
        self.assertEqual(created_user.org_group, 'technique')
        self.assertTrue(created_user.check_password('SecretPass123!'))


class LoginNameTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username='abbed.tshuli',
            password='Tshuli2026',
            first_name='Abbed',
            last_name='Tshuli',
            email='abbed.tshuli@agencemwinda.com',
            role='agent',
            direction='metal_design',
        )

    def test_login_accepts_display_name(self):
        response = self.client.post(reverse('login'), {
            'username': 'Abbed Tshuli',
            'password': 'Tshuli2026',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            self.agent.id,
        )

    def test_login_rejects_wrong_password(self):
        request = RequestFactory().post('/login/')
        user = authenticate_login(request, 'Abbed.Tshuli', 'tshuli2026')
        self.assertIsNone(user)
