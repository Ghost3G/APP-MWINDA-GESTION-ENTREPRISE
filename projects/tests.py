from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .models import Project
from .models import AgentTimeEntry, ProjectAssignmentNotification

User = get_user_model()


class ProjectsFeatureTests(TestCase):
    def setUp(self):
        self.directeur = User.objects.create_user(
            username='boss',
            password='testpass123',
            email='boss@example.com',
            role='directeur',
            direction='technique',
        )
        self.agent = User.objects.create_user(
            username='agent1',
            password='testpass123',
            email='agent1@example.com',
            role='agent',
            direction='design',
        )

    def test_directeur_can_create_project(self):
        commercial = User.objects.create_user(
            username='commercial1',
            password='testpass123',
            email='commercial1@example.com',
            role='agent',
            direction='branding',
            org_group='commercial',
            grade='Agent Commercial',
        )
        self.client.login(username='boss', password='testpass123')
        response = self.client.post(
            reverse('projects_list'),
            {
                'name': 'Projet Test',
                'description': 'Description test',
                'start_date': '2026-04-01',
                'end_date': '2026-04-30',
                'status': 'pending',
                'branch': 'metal_design',
                'members': [self.agent.id],
                'commercial_agent': commercial.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(name='Projet Test').exists())
        self.assertTrue(ProjectAssignmentNotification.objects.filter(user=self.agent, is_read=False).exists())

    def test_project_assignment_notification_is_marked_read_on_projects_page(self):
        project = Project.objects.create(
            name='Projet Notification',
            description='Description test',
            start_date='2026-04-01',
            end_date='2026-04-30',
            status='pending',
            manager=self.directeur,
        )
        project.members.add(self.agent)
        ProjectAssignmentNotification.objects.create(user=self.agent, project=project)

        self.client.login(username='agent1', password='testpass123')
        response = self.client.get(reverse('projects_list'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProjectAssignmentNotification.objects.filter(user=self.agent, is_read=False).exists())

    def test_agent_cannot_create_project(self):
        self.client.login(username='agent1', password='testpass123')
        response = self.client.post(
            reverse('projects_list'),
            {
                'name': 'Projet Interdit',
                'description': 'Description test',
                'start_date': '2026-04-01',
                'end_date': '2026-04-30',
                'status': 'pending',
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_task_timer_start_and_complete(self):
        self.client.login(username='agent1', password='testpass123')

        start_response = self.client.post(
            reverse('start_task_timer'),
            {'task_label': 'Conception du logo'},
        )
        self.assertEqual(start_response.status_code, 200)

        task_entry = AgentTimeEntry.objects.get(user=self.agent, entry_type='task', ended_at__isnull=True)
        task_entry.started_at = timezone.now() - timedelta(minutes=2)
        task_entry.save(update_fields=['started_at'])

        complete_response = self.client.post(
            reverse('complete_task_timer'),
            {'task_label': 'Conception du logo'},
        )
        self.assertEqual(complete_response.status_code, 200)

        task_entry.refresh_from_db()
        self.assertIsNotNone(task_entry.ended_at)
        self.assertGreaterEqual(task_entry.duration_seconds, 120)

    def test_pause_timer_toggle(self):
        self.client.login(username='agent1', password='testpass123')

        start_pause = self.client.post(reverse('toggle_pause_timer'))
        self.assertEqual(start_pause.status_code, 200)
        pause_entry = AgentTimeEntry.objects.get(user=self.agent, entry_type='pause', ended_at__isnull=True)

        pause_entry.started_at = timezone.now() - timedelta(seconds=30)
        pause_entry.save(update_fields=['started_at'])

        stop_pause = self.client.post(reverse('toggle_pause_timer'))
        self.assertEqual(stop_pause.status_code, 200)

        pause_entry.refresh_from_db()
        self.assertIsNotNone(pause_entry.ended_at)
        self.assertGreaterEqual(pause_entry.duration_seconds, 30)

    def test_member_can_view_project_detail(self):
        project = Project.objects.create(
            name='Projet Détail',
            description='Description complète',
            start_date='2026-04-01',
            end_date='2026-04-30',
            status='pending',
            manager=self.directeur,
        )
        project.members.add(self.agent)

        self.client.login(username='agent1', password='testpass123')
        response = self.client.get(reverse('project_detail', args=[project.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Projet Détail')
