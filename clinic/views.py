from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse
import csv
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Q
from .models import Patient, Visit, Medicine, Prescription, Receipt, ReceiptItem, FollowUp
from .serializers import PatientSerializer, VisitSerializer, MedicineSerializer, PrescriptionSerializer, ReceiptSerializer, ReceiptItemSerializer, FollowUpSerializer
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


class FollowUpViewSet(viewsets.ModelViewSet):
    """
    ViewSet for FollowUp records with a complete workflow:
    1. Create follow-up (receptionist records condition)
    2. List pending reassignments (reception reviews)
    3. Reassign to doctor (reception sends)
    4. Doctor sees reassigned follow-ups
    5. Doctor completes with re-diagnosis and new prescriptions
    """
    queryset = FollowUp.objects.all()
    serializer_class = FollowUpSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['patient__patient_id', 'patient__name', 'patient__phone']
    ordering_fields = ['follow_up_date', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            queryset = queryset.filter(patient__patient_id=patient_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset.order_by('-follow_up_date')

    @action(detail=False, methods=['post'], url_path='search-patient')
    def search_patient(self, request):
        """
        Look up a patient by their patient_id (SCH-XXXX-XXXXX)
        and return their info + follow-up history.
        """
        patient_id = request.data.get('patient_id', '').strip()
        if not patient_id:
            return Response({'error': 'Patient ID is required'}, status=400)
        try:
            patient = Patient.objects.get(patient_id=patient_id)
            # Get patient's visits history
            visits = patient.visits.all().order_by('-created_at')
            # Get follow-ups
            follow_ups = FollowUp.objects.filter(patient=patient).order_by('-follow_up_date')
            return Response({
                'patient': PatientSerializer(patient).data,
                'visits': VisitSerializer(visits, many=True).data,
                'follow_ups': FollowUpSerializer(follow_ups, many=True).data,
            })
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)

    @action(detail=False, methods=['patch'], url_path='update-patient')
    def update_patient(self, request):
        """
        Update patient info (name, phone, age, date_of_birth, gender, address,
        emergency_contact_name, emergency_contact_phone).
        Used during follow-up to edit patient details.
        """
        patient_id = request.data.get('patient_id', '').strip()
        if not patient_id:
            return Response({'error': 'Patient ID is required'}, status=400)
        try:
            patient = Patient.objects.get(patient_id=patient_id)
            # Update editable fields
            for field in ['name', 'phone', 'age', 'date_of_birth', 'gender', 'address',
                          'emergency_contact_name', 'emergency_contact_phone']:
                if field in request.data:
                    setattr(patient, field, request.data[field])
            patient.save()
            return Response({
                'message': 'Patient updated successfully',
                'patient': PatientSerializer(patient).data
            })
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=404)

    @action(detail=True, methods=['post'], url_path='reassign')
    def reassign_to_doctor(self, request, pk=None):
        """
        Receptionist reassigns a pending follow-up to a doctor.
        Also creates a follow-up visit for the doctor's queue.
        """
        followup = self.get_object()
        
        if followup.status != 'pending_reassign':
            return Response(
                {'error': f'Cannot reassign follow-up with status "{followup.status}"'},
                status=400
            )
        
        # Create a follow-up visit for the doctor
        today = timezone.now().date()
        visit = Visit.objects.create(
            patient=followup.patient,
            visit_type='followup',
            symptoms=followup.condition_after_treatment,
            status='waiting',
            visit_date=today,
            notes=f"Follow-up: {followup.condition_after_treatment[:200]}"
        )
        
        # Link visit to follow-up
        followup.visit = visit
        
        # Update follow-up status
        followup.status = 'reassigned'
        followup.reassigned_at = timezone.now()
        followup.reassigned_by = request.data.get('reassigned_by', request.user.username if request.user.is_authenticated else 'Receptionist')
        followup.save()
        
        return Response({
            'message': 'Follow-up reassigned to doctor',
            'followup': FollowUpSerializer(followup).data,
            'visit': VisitSerializer(visit).data,
        })

    @action(detail=True, methods=['post'], url_path='start-doctor-review')
    def start_doctor_review(self, request, pk=None):
        """
        Doctor starts reviewing a reassigned follow-up.
        Sets status to in_progress. Also marks the linked visit as in_progress.
        """
        followup = self.get_object()
        
        if followup.status != 'reassigned':
            return Response(
                {'error': f'Cannot start review. Status is "{followup.status}"'},
                status=400
            )
        
        followup.status = 'in_progress'
        followup.save()
        
        # Also mark linked visit as in_progress
        if followup.visit:
            followup.visit.status = 'in_progress'
            followup.visit.save()
        
        return Response({
            'message': 'Doctor review started',
            'followup': FollowUpSerializer(followup).data,
        })

    @action(detail=True, methods=['post'], url_path='complete-doctor-review')
    def complete_doctor_review(self, request, pk=None):
        """
        Doctor completes the follow-up review with:
        - re_diagnosis
        - doctor_notes
        - new prescriptions (optional)
        Marks follow-up as completed and sends linked visit to pharmacy.
        """
        followup = self.get_object()
        
        if followup.status not in ['reassigned', 'in_progress']:
            return Response(
                {'error': f'Cannot complete. Status is "{followup.status}"'},
                status=400
            )
        
        # Save doctor's assessment
        re_diagnosis = request.data.get('re_diagnosis', '')
        doctor_notes = request.data.get('doctor_notes', '')
        
        if re_diagnosis:
            followup.re_diagnosis = re_diagnosis
        if doctor_notes:
            followup.doctor_notes = doctor_notes
        
        followup.status = 'completed'
        followup.completed_at = timezone.now()
        followup.save()
        
        # Update linked visit
        if followup.visit:
            followup.visit.diagnosis = re_diagnosis or followup.visit.diagnosis
            followup.visit.notes = doctor_notes or followup.visit.notes
            followup.visit.status = 'completed'
            followup.visit.save()
        
        # Create prescriptions if provided
        prescriptions_data = request.data.get('prescriptions', [])
        prescriptions_created = []
        for p in prescriptions_data:
            if not p.get('medicine_id') or not p.get('dosage') or p.get('quantity', 0) < 1:
                continue
            pres = Prescription.objects.create(
                visit=followup.visit,
                medicine_id=p['medicine_id'],
                dosage=p['dosage'],
                quantity_prescribed=p['quantity'],
            )
            prescriptions_created.append(PrescriptionSerializer(pres).data)
        
        return Response({
            'message': 'Follow-up review completed. Sent to pharmacy.',
            'followup': FollowUpSerializer(followup).data,
            'prescriptions_created': prescriptions_created,
        })

    @action(detail=False, methods=['get'], url_path='pending-reassign')
    def pending_reassign(self, request):
        """Get all follow-ups pending reassignment (for receptionist view)."""
        followups = FollowUp.objects.filter(status='pending_reassign').order_by('-created_at')
        serializer = self.get_serializer(followups, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='doctor-queue')
    def doctor_queue(self, request):
        """Get all follow-ups reassigned to doctor (for doctor's view)."""
        followups = FollowUp.objects.filter(
            status__in=['reassigned', 'in_progress']
        ).order_by('-follow_up_date')
        serializer = self.get_serializer(followups, many=True)
        return Response(serializer.data)


# -------------------- STATS VIEWSET --------------------
from rest_framework.viewsets import ViewSet

class StatsViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='reception')
    def reception_stats(self, request):
        data = get_reception_stats()
        recent = data.pop('recent_visits', [])
        data['recent_visits'] = VisitSerializer(recent, many=True).data
        
        # Add follow-up pending count
        data['pending_followups'] = FollowUp.objects.filter(status='pending_reassign').count()
        
        return Response(data)

    @action(detail=False, methods=['get'], url_path='doctor')
    def doctor_stats(self, request):
        data = get_doctor_stats()
        queue = data.pop('queue')
        data['queue'] = VisitSerializer(queue, many=True).data
        
        # Add doctor's follow-up queue count
        data['followup_queue'] = FollowUp.objects.filter(
            status__in=['reassigned', 'in_progress']
        ).count()
        
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