from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from users.permissions import can_edit_machines

from .models import Machine

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class MachinesAccessTests(TestCase):
    def setUp(self):
        self.dt = User.objects.create_user(
            username='ibrahim.japhete',
            password='testpass123',
            email='japhete@example.com',
            role='directeur',
            direction='metal_design',
        )
        self.agent = User.objects.create_user(
            username='agent.test',
            password='testpass123',
            email='agent@example.com',
            role='agent',
            direction='branding',
        )
        self.machine = Machine.objects.create(name='Découpe laser')

    def test_dt_can_edit(self):
        self.assertTrue(can_edit_machines(self.dt))
        self.assertFalse(can_edit_machines(self.agent))

    def test_louise_can_edit(self):
        louise = User.objects.create_user(
            username='louise.netando',
            password='testpass123',
            email='louise@example.com',
            role='agent',
            direction='metal_design',
        )
        self.assertTrue(can_edit_machines(louise))

    def test_agent_cannot_create(self):
        self.client.login(username='agent.test', password='testpass123')
        response = self.client.post(
            reverse('machines_list'),
            {'action': 'create_machine', 'name': 'Presse'},
        )
        self.assertEqual(Machine.objects.filter(name='Presse').count(), 0)
        self.assertEqual(response.status_code, 302)

    def test_dt_can_create(self):
        self.client.login(username='ibrahim.japhete', password='testpass123')
        response = self.client.post(
            reverse('machines_list'),
            {'action': 'create_machine', 'name': 'Presse'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Machine.objects.filter(name='Presse').exists())

    def test_dt_can_delete(self):
        self.client.login(username='ibrahim.japhete', password='testpass123')
        response = self.client.post(
            reverse('machines_list'),
            {
                'action': 'delete_machine',
                'machine_id': self.machine.id,
                'confirm': 'SUPPRIMER',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.machine.refresh_from_db()
        self.assertFalse(self.machine.is_active)

    def test_agent_cannot_delete(self):
        self.client.login(username='agent.test', password='testpass123')
        response = self.client.post(
            reverse('machines_list'),
            {
                'action': 'delete_machine',
                'machine_id': self.machine.id,
                'confirm': 'SUPPRIMER',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.machine.refresh_from_db()
        self.assertTrue(self.machine.is_active)
