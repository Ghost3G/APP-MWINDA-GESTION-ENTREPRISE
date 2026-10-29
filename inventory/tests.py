from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from projects.models import Project

from .models import DeliveryShipment, Supplier
from .views import stock_dashboard, stock_logistics, stock_suppliers

User = get_user_model()


class StockLogisticsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.manager = User.objects.create_user(
            username='joseph.mbuyu',
            password='testpass123',
            email='joseph@example.com',
            role='agent',
            org_group='logistique',
            direction='metal_design',
        )
        self.agent = User.objects.create_user(
            username='agent-stock',
            password='testpass123',
            email='agent-stock@example.com',
            role='agent',
            org_group='technique',
            direction='metal_design',
        )
        today = timezone.localdate()
        self.project = Project.objects.create(
            name='Projet Livraison Test',
            description='Test logistique',
            start_date=today,
            end_date=today + timedelta(days=3),
            status='awaiting_delivery',
            branch='metal_design',
            manager=self.manager,
        )

    def _request(self, view, user, method='get', path='/', data=None):
        if method == 'post':
            request = self.factory.post(path, data or {})
        else:
            request = self.factory.get(path)
        request.user = user
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return view(request)

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        }
    )
    def test_logistics_user_can_open_sections(self):
        for view, path in (
            (stock_dashboard, '/stock/'),
            (stock_suppliers, '/stock/fournisseurs/'),
            (stock_logistics, '/stock/logistique/'),
        ):
            response = self._request(view, self.manager, path=path)
            self.assertEqual(response.status_code, 200)

    def test_other_agent_cannot_access_stock(self):
        response = self._request(stock_logistics, self.agent, path='/stock/logistique/')
        self.assertEqual(response.status_code, 302)

    def test_create_supplier_and_delivery(self):
        response = self._request(
            stock_suppliers,
            self.manager,
            method='post',
            path='/stock/fournisseurs/',
            data={
                'action': 'create_supplier',
                'name': 'Fournisseur Métal Test',
                'contact_name': 'Jean',
                'phone': '0990000000',
                'city': 'Kinshasa',
                'specialty': 'metal',
                'lead_time_days': '3',
                'payment_terms': '50% avance',
            },
        )
        self.assertEqual(response.status_code, 302)
        supplier = Supplier.objects.get(name='Fournisseur Métal Test')
        self.assertEqual(supplier.specialty, 'metal')
        self.assertEqual(supplier.lead_time_days, 3)

        response = self._request(
            stock_logistics,
            self.manager,
            method='post',
            path='/stock/logistique/',
            data={
                'action': 'create_delivery',
                'project_id': self.project.id,
                'status': 'scheduled',
                'scheduled_date': timezone.localdate().isoformat(),
                'driver_name': 'Paul',
                'recipient_name': 'Client',
                'destination': 'Gombe',
            },
        )
        self.assertEqual(response.status_code, 302)
        shipment = DeliveryShipment.objects.get(project=self.project)
        self.assertEqual(shipment.status, 'scheduled')
        self.assertEqual(shipment.driver_name, 'Paul')
