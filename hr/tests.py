from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from hr.models import JobApplication, LeaveRequest
from hr.permissions import is_hr_manager
from hr.phase2_views import hr_recruitment
from hr.views import hr_dashboard, hr_documents, hr_leaves

User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class HRModuleTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.drh = User.objects.create_user(
            username='bastin.musila',
            password='testpass123',
            email='bastin@example.com',
            role='admin',
            org_group='rh',
            job_title='DRH',
            first_name='Bastin',
            last_name='Musila',
            is_staff=True,
            is_superuser=True,
        )
        self.agent = User.objects.create_user(
            username='agent.rh',
            password='testpass123',
            email='agent.rh@example.com',
            role='agent',
            org_group='technique',
            first_name='Agent',
            last_name='Test',
        )

    def test_bastin_is_hr_manager(self):
        self.assertTrue(is_hr_manager(self.drh))
        self.assertFalse(is_hr_manager(self.agent))

    def test_hr_dashboard_visible_to_everyone(self):
        request = self.factory.get(reverse('hr_dashboard'))
        request.user = self.agent
        response = hr_dashboard(request)
        self.assertEqual(response.status_code, 200)

    def test_agent_can_request_leave_and_drh_can_approve(self):
        today = timezone.localdate()
        request = self.factory.post(reverse('hr_leaves'), {
            'action': 'create',
            'leave_type': LeaveRequest.TYPE_ANNUAL,
            'start_date': today.isoformat(),
            'end_date': (today + timedelta(days=2)).isoformat(),
            'reason': 'Repos',
        })
        request.user = self.agent
        # messages middleware stub
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        response = hr_leaves(request)
        self.assertEqual(response.status_code, 302)
        leave = LeaveRequest.objects.get(user=self.agent)
        self.assertEqual(leave.status, LeaveRequest.STATUS_PENDING)

        approve_req = self.factory.post(reverse('hr_leaves'), {
            'action': 'approve',
            'leave_id': leave.id,
        })
        approve_req.user = self.drh
        SessionMiddleware(lambda r: None).process_request(approve_req)
        approve_req.session.save()
        approve_req._messages = FallbackStorage(approve_req)
        approve = hr_leaves(approve_req)
        self.assertEqual(approve.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.STATUS_APPROVED)

    def test_agent_cannot_manage_documents_upload(self):
        request = self.factory.post(reverse('hr_documents'), {
            'action': 'upload',
            'user_id': self.agent.id,
            'title': 'CV',
            'kind': 'cv',
        })
        request.user = self.agent
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        response = hr_documents(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.agent.hr_documents.count(), 0)

    def test_drh_can_create_job_application(self):
        request = self.factory.post(reverse('hr_recruitment'), {
            'action': 'create',
            'full_name': 'Candidat Test',
            'position': 'Technicien',
            'status': 'received',
        })
        request.user = self.drh
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        response = hr_recruitment(request)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JobApplication.objects.filter(full_name='Candidat Test').exists())

    def test_agent_cannot_access_recruitment(self):
        request = self.factory.get(reverse('hr_recruitment'))
        request.user = self.agent
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        response = hr_recruitment(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('hr_dashboard'))
