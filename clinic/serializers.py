from rest_framework import serializers
from .models import Patient, Visit, Medicine, Prescription, Receipt, ReceiptItem

class DateOnlyField(serializers.DateField):
    def to_internal_value(self, value):
        if isinstance(value, str) and 'T' in value:
            value = value.split('T')[0]
        return super().to_internal_value(value)

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ('patient_id', 'created_at')

class VisitSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source='patient.name')
    patient_phone = serializers.ReadOnlyField(source='patient.phone')
    patient_id = serializers.ReadOnlyField(source='patient.patient_id')
    patient_address = serializers.ReadOnlyField(source='patient.address')
    patient_emergency_contact = serializers.SerializerMethodField()
    visit_date = DateOnlyField()
    balance_due = serializers.ReadOnlyField()

    class Meta:
        model = Visit
        fields = '__all__'

    def get_patient_emergency_contact(self, obj):
        return {
            'name': obj.patient.emergency_contact_name,
            'phone': obj.patient.emergency_contact_phone
        }

class MedicineSerializer(serializers.ModelSerializer):
    stock_percentage = serializers.ReadOnlyField()
    stock_status = serializers.ReadOnlyField()
    total_value = serializers.ReadOnlyField()

    class Meta:
        model = Medicine
        fields = '__all__'

class PrescriptionSerializer(serializers.ModelSerializer):
    medicine_name = serializers.ReadOnlyField(source='medicine.name')
    medicine_price = serializers.ReadOnlyField(source='medicine.price_per_unit')
    visit_ticket = serializers.ReadOnlyField(source='visit.ticket_number')
    visit_patient_name = serializers.ReadOnlyField(source='visit.patient.name')
    visit_total_amount = serializers.ReadOnlyField(source='visit.total_amount')
    visit_paid_amount = serializers.ReadOnlyField(source='visit.paid_amount')
    visit_balance_due = serializers.ReadOnlyField(source='visit.balance_due')

    class Meta:
        model = Prescription
        fields = '__all__'

class ReceiptItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptItem
        fields = '__all__'

class ReceiptSerializer(serializers.ModelSerializer):
    items = ReceiptItemSerializer(many=True, read_only=True)

    class Meta:
        model = Receipt
        fields = '__all__'
