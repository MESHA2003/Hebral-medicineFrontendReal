from django.db import models
from django.utils import timezone
from .utils import PatientIDGenerator

class Patient(models.Model):
    GENDER_CHOICES = (('M', 'Male'), ('F', 'Female'), ('O', 'Other'))
    patient_id = models.CharField(max_length=50, unique=True, blank=True, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    age = models.PositiveIntegerField(help_text="Age in years")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    address = models.TextField(blank=True, help_text="Village / District / Street")
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.patient_id:
            self.patient_id = PatientIDGenerator.generate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient_id} - {self.name}"

class Visit(models.Model):
    VISIT_TYPE_CHOICES = (('new', 'New Patient'), ('followup', 'Follow-up'))
    STATUS_CHOICES = (
        ('waiting', 'Waiting'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed (Send to Pharmacy)'),
        ('dispensed', 'Dispensed'),
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='visits')
    visit_type = models.CharField(max_length=10, choices=VISIT_TYPE_CHOICES, default='new')
    visit_date = models.DateField(default=timezone.now)
    symptoms = models.TextField()
    diagnosis = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    ticket_number = models.CharField(max_length=20, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            last = Visit.objects.order_by('-id').first()
            next_seq = (last.id + 1) if last else 1
            self.ticket_number = PatientIDGenerator.generate_ticket_number(next_seq)
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return self.total_amount - self.paid_amount

    def __str__(self):
        return f"{self.ticket_number} - {self.patient.name} ({self.get_visit_type_display()})"

class Medicine(models.Model):
    CATEGORY_CHOICES = (
        ('liquid', 'Liquid'),
        ('powder', 'Powder'),
        ('capsules', 'Capsules'),
        ('raw_herbs', 'Raw Herbs'),
    )
    UNIT_CHOICES = (
        ('ml', 'ml'),
        ('liters', 'Liters'),
        ('g', 'g'),
        ('kg', 'kg'),
        ('pieces', 'Pieces'),
        ('bottles', 'Bottles'),
        ('bundles', 'Bundles'),
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='capsules')
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='pieces')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    source = models.CharField(max_length=100, blank=True, default='')
    stock_quantity = models.PositiveIntegerField(default=0)
    total_capacity = models.PositiveIntegerField(default=0, help_text="Maximum stock capacity (100% level). Must be >= stock_quantity.")
    reorder_level = models.PositiveIntegerField(default=10)
    critical_level = models.PositiveIntegerField(default=5)
    expiry_date = models.DateField(null=True, blank=True)
    date_added = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True, default='')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.total_capacity > 0 and self.stock_quantity > self.total_capacity:
            raise ValidationError({
                'stock_quantity': f'Stock quantity ({self.stock_quantity}) cannot exceed total capacity ({self.total_capacity}).'
            })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def stock_percentage(self):
        if self.total_capacity == 0:
            return 0
        pct = round((self.stock_quantity / self.total_capacity) * 100, 1)
        return min(pct, 100.0)

    @property
    def stock_status(self):
        if self.total_capacity == 0:
            return 'ok'
        percentage = self.stock_percentage
        if percentage <= 20:
            return 'critical'
        elif percentage <= 40:
            return 'low'
        else:
            return 'ok'

    @property
    def total_value(self):
        return self.price_per_unit * self.stock_quantity

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

class Prescription(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='prescriptions')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    dosage = models.CharField(max_length=100)
    quantity_prescribed = models.PositiveIntegerField()
    quantity_dispensed = models.PositiveIntegerField(default=0)
    dispensed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_fully_dispensed(self):
        return self.quantity_dispensed >= self.quantity_prescribed

    def __str__(self):
        return f"{self.medicine.name} for {self.visit.patient.name}"

class Receipt(models.Model):
    receipt_number = models.CharField(max_length=20, unique=True, blank=True)
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='receipts')
    patient_name = models.CharField(max_length=100)
    patient_id = models.CharField(max_length=50)
    ticket_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            last = Receipt.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.receipt_number = f"RCP-{next_num:06d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} - {self.patient_name}"

class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    medicine_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.medicine_name} ({self.quantity})"


class FollowUp(models.Model):
    """
    Tracks follow-up visits for patients after their initial treatment.
    Supports a complete workflow:
      1. Receptionist searches patient, records condition, creates follow-up
      2. Follow-up appears in reception's "pending reassignment" list
      3. Receptionist reviews and reassigns to doctor
      4. Doctor sees reassigned follow-ups, re-diagnoses, adds new prescriptions
      5. Doctor completes and sends to pharmacy
    """
    FOLLOWUP_STATUS_CHOICES = (
        ('pending_reassign', 'Pending Reassignment'),  # Just created, waiting for reception to reassign
        ('reassigned', 'Reassigned to Doctor'),         # Reception has sent to doctor
        ('in_progress', 'Doctor In Progress'),           # Doctor is working on it
        ('completed', 'Completed'),                      # Doctor finished (sent to pharmacy)
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='follow_ups')
    visit = models.ForeignKey(Visit, on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_ups')
    follow_up_date = models.DateField(default=timezone.now)
    condition_after_treatment = models.TextField(blank=True, help_text="Patient's condition after treatment")
    notes = models.TextField(blank=True)

    # Workflow status
    status = models.CharField(max_length=20, choices=FOLLOWUP_STATUS_CHOICES, default='pending_reassign')

    # Reassignment tracking (receptionist)
    reassigned_at = models.DateTimeField(null=True, blank=True)
    reassigned_by = models.CharField(max_length=100, blank=True, help_text="Receptionist who reassigned")

    # Doctor's follow-up assessment
    re_diagnosis = models.TextField(blank=True, help_text="Doctor's re-diagnosis during follow-up")
    doctor_notes = models.TextField(blank=True, help_text="Doctor's additional notes during follow-up")
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FollowUp: {self.patient.patient_id} - {self.follow_up_date} ({self.get_status_display()})"