from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from alerts.services import collect_team_alerts, count_actionable_alerts
from projects.models import Project

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class AlertsCenterTests(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username='agent.alert',
            password='testpass123',
            email='agent@example.com',
            role='agent',
            direction='branding',
        )
        self.manager = User.objects.create_user(
            username='mgr.alert',
            password='testpass123',
            email='mgr@example.com',
            role='directeur',
            direction='metal_design',
        )
        self.project = Project.objects.create(
            name='Projet Retard Test',
            description='Test',
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() - timedelta(days=2),
            status='progress',
            manager=self.manager,
        )

    def test_collect_includes_overdue_project(self):
        alerts = collect_team_alerts()
        titles = [a['title'] for a in alerts]
        self.assertTrue(any('Projet Retard Test' in t for t in titles))
        self.assertGreaterEqual(count_actionable_alerts(), 1)

    def test_alerts_url_resolves(self):
        self.assertEqual(reverse('alerts_center'), '/alerts/')

    def test_center_requires_login(self):
        response = self.client.get(reverse('alerts_center'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)
