from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q
from .models import Patient, Visit, Medicine, Prescription
from .serializers import PatientSerializer, VisitSerializer, MedicineSerializer, PrescriptionSerializer
from .stats_utils import get_pharmacy_stats  # import the function

class IsPharmacyOrAdmin(IsAdminUser):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return request.user.role in ['pharmacy', 'admin']
        return False

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        patient = self.get_object()
        visits = patient.visits.all().order_by('-created_at')
        serializer = VisitSerializer(visits, many=True)
        return Response(serializer.data)

class VisitViewSet(viewsets.ModelViewSet):
    queryset = Visit.objects.all()
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['ticket_number', 'patient__name', 'patient__phone']
    ordering_fields = ['created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')
        if status_param == 'completed':
            return queryset.filter(status='completed').order_by('-created_at')
        days = self.request.query_params.get('days', 30)
        if days:
            cutoff = timezone.now().date() - timedelta(days=int(days))
            queryset = queryset.filter(created_at__date__gte=cutoff)
        search = self.request.query_params.get('search')
        if search:
            return Visit.objects.filter(
                Q(ticket_number__icontains=search) |
                Q(patient__name__icontains=search) |
                Q(patient__phone__icontains=search)
            ).order_by('-created_at')
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def complete_consultation(self, request, pk=None):
        visit = self.get_object()
        visit.status = 'completed'
        visit.save()
        return Response({'status': 'completed'})

    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        visits = self.get_queryset().filter(status__in=['completed', 'dispensed']).order_by('-created_at')
        serializer = self.get_serializer(visits, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-ticket/(?P<ticket_number>[^/.]+)')
    def by_ticket(self, request, ticket_number=None):
        try:
            visit = Visit.objects.get(ticket_number=ticket_number)
            serializer = self.get_serializer(visit)
            return Response(serializer.data)
        except Visit.DoesNotExist:
            return Response({'error': 'Ticket not found'}, status=404)

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        else:
            return [IsPharmacyOrAdmin()]

class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        visit_id = self.request.query_params.get('visit')
        if visit_id:
            queryset = queryset.filter(visit_id=visit_id)
        return queryset

    @action(detail=True, methods=['post'])
    def dispense(self, request, pk=None):
        prescription = self.get_object()
        qty = int(request.data.get('quantity', 0))
        if qty <= 0 or qty > (prescription.quantity_prescribed - prescription.quantity_dispensed):
            return Response({'error': 'Invalid quantity'}, status=400)
        prescription.quantity_dispensed += qty
        if prescription.quantity_dispensed >= prescription.quantity_prescribed:
            prescription.dispensed_at = timezone.now()
        prescription.save()
        medicine = prescription.medicine
        medicine.stock_quantity -= qty
        medicine.save()
        visit = prescription.visit
        if all(p.is_fully_dispensed for p in visit.prescriptions.all()):
            visit.status = 'dispensed'
            visit.save()
        return Response({'status': 'dispensed', 'remaining': prescription.quantity_prescribed - prescription.quantity_dispensed})

# -------------------- STATS VIEWSET --------------------
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from .stats_utils import get_pharmacy_stats, get_reception_stats, get_doctor_stats, get_admin_stats

class StatsViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='reception')
    def reception_stats(self, request):
        data = get_reception_stats()
        recent = data.pop('recent_visits', [])
        data['recent_visits'] = VisitSerializer(recent, many=True).data
        return Response(data)

    @action(detail=False, methods=['get'], url_path='doctor')
    def doctor_stats(self, request):
        data = get_doctor_stats()
        queue = data.pop('queue')
        data['queue'] = VisitSerializer(queue, many=True).data
        return Response(data)

    @action(detail=False, methods=['get'], url_path='pharmacy')
    def pharmacy_stats(self, request):
        data = get_pharmacy_stats()
        pending = data.pop('pending_prescriptions')
        fully = data.pop('fully_dispensed_prescriptions')
        return Response({
            'pending_count': data['pending_count'],
            'fully_dispensed_count': data['fully_dispensed_count'],
            'total_units_dispensed': data['total_units_dispensed'],
            'pending_prescriptions': PrescriptionSerializer(pending, many=True).data,
            'fully_dispensed_prescriptions': PrescriptionSerializer(fully, many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='admin')
    def admin_stats(self, request):
        data = get_admin_stats()
        low_stock = data.pop('low_stock_medicines')
        top_medicines = data.get('top_medicines', [])
        data['low_stock_medicines'] = MedicineSerializer(low_stock, many=True).data
        # top_medicines already has name and count from stats_utils, just pass it through
        data['top_medicines'] = top_medicines
        # Generate weekly visits
        last7 = []
        for i in range(6, -1, -1):
            d = timezone.now().date() - timedelta(days=i)
            count = Visit.objects.filter(created_at__date=d).count()
            last7.append({'date': d.strftime('%m-%d'), 'count': count})
        data['weekly_visits'] = last7
        return Response(data)