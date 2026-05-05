from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse
import csv
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q
from .models import Patient, Visit, Medicine, Prescription, Receipt, ReceiptItem
from .serializers import PatientSerializer, VisitSerializer, MedicineSerializer, PrescriptionSerializer, ReceiptSerializer, ReceiptItemSerializer
from .stats_utils import get_pharmacy_stats, get_reception_stats, get_doctor_stats, get_admin_stats

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

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_consultation(self, request, pk=None):
        """
        Complete consultation. Optionally send to pharmacy (default) or back to reception.
        """
        visit = self.get_object()
        destination = request.data.get('destination', 'pharmacy')
        if destination == 'reception':
            visit.status = 'waiting'
        else:
            visit.status = 'completed'
        visit.save()
        diagnosis = request.data.get('diagnosis')
        notes = request.data.get('notes')
        if diagnosis is not None:
            visit.diagnosis = diagnosis
        if notes is not None:
            visit.notes = notes
        visit.save()
        return Response({'status': visit.status, 'destination': destination})

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

    @action(detail=True, methods=['post'], url_path='dispense-all')
    def dispense_all(self, request, pk=None):
        """
        Dispense ALL prescriptions for a visit at once, create ONE receipt with all items.
        """
        visit = self.get_object()
        prescriptions = visit.prescriptions.all()
        if not prescriptions.exists():
            return Response({'error': 'No prescriptions found for this visit'}, status=400)

        total_cost = 0
        receipt_items_data = []

        for pres in prescriptions:
            remaining = pres.quantity_prescribed - pres.quantity_dispensed
            if remaining <= 0:
                continue

            qty = remaining
            cost = qty * pres.medicine.price_per_unit
            total_cost += cost

            # Dispense the prescription
            pres.quantity_dispensed += qty
            pres.dispensed_at = timezone.now()
            pres.save()

            # Reduce stock
            med = pres.medicine
            med.stock_quantity -= qty
            med.save()

            receipt_items_data.append({
                'medicine_name': med.name,
                'quantity': qty,
                'unit_price': float(med.price_per_unit),
                'total': float(cost),
            })

        # Update visit totals
        visit.total_amount += total_cost
        visit.status = 'dispensed'
        visit.save()

        # Create ONE receipt with all items
        receipt = Receipt.objects.create(
            visit=visit,
            patient_name=visit.patient.name,
            patient_id=visit.patient.patient_id,
            ticket_number=visit.ticket_number,
        )
        for item_data in receipt_items_data:
            ReceiptItem.objects.create(receipt=receipt, **item_data)

        return Response({
            'status': 'dispensed',
            'receipt': ReceiptSerializer(receipt).data,
        })

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

# -------------------- STATS VIEWSET --------------------
from rest_framework.viewsets import ViewSet

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
        pending_visits = data.pop('pending_visits', [])
        dispensed_visits = data.pop('dispensed_visits', [])
        return Response({
            'pending_count': data['pending_count'],
            'fully_dispensed_count': data['fully_dispensed_count'],
            'total_units_dispensed': data['total_units_dispensed'],
            'pending_visits': VisitSerializer(pending_visits, many=True).data,
            'dispensed_visits': VisitSerializer(dispensed_visits, many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='admin')
    def admin_stats(self, request):
        data = get_admin_stats()
        low_stock = data.pop('low_stock_medicines')
        top_medicines = data.get('top_medicines', [])
        data['low_stock_medicines'] = MedicineSerializer(low_stock, many=True).data
        data['top_medicines'] = top_medicines
        last7 = []
        for i in range(6, -1, -1):
            d = timezone.now().date() - timedelta(days=i)
            count = Visit.objects.filter(created_at__date=d).count()
            last7.append({'date': d.strftime('%m-%d'), 'count': count})
        data['weekly_visits'] = last7
        return Response(data)

    @action(detail=False, methods=['get'], url_path='full-report')
    def full_report(self, request):
        patients = Patient.objects.all().values(
            'patient_id', 'name', 'phone', 'age', 'gender', 'address', 'created_at'
        )
        visits = Visit.objects.all().values(
            'ticket_number', 'patient__name', 'status', 'created_at', 'updated_at'
        )
        prescriptions = Prescription.objects.all().values(
            'visit__ticket_number', 'medicine__name', 'quantity_prescribed', 'quantity_dispensed'
        )
        medicines = Medicine.objects.all().values(
            'name', 'stock_quantity', 'price_per_unit', 'category', 'unit'
        )
        receipts = Receipt.objects.all().values(
            'receipt_number', 'ticket_number', 'patient_name', 'created_at'
        )
        report = {
            'patients': list(patients),
            'visits': list(visits),
            'prescriptions': list(prescriptions),
            'medicines': list(medicines),
            'receipts': list(receipts),
        }
        return Response(report)