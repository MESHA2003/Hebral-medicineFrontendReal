from rest_framework import serializers
from .models import Patient, Visit, Medicine, Prescription, Receipt, ReceiptItem, FollowUp

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

    def validate(self, data):
        stock_qty = data.get('stock_quantity', self.instance.stock_quantity if self.instance else 0)
        total_cap = data.get('total_capacity', self.instance.total_capacity if self.instance else 0)
        if total_cap > 0 and stock_qty > total_cap:
            raise serializers.ValidationError({
                'stock_quantity': f'Stock quantity ({stock_qty}) cannot exceed total capacity ({total_cap}).'
            })
        return data

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


class FollowUpSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source='patient.name')
    patient_phone = serializers.ReadOnlyField(source='patient.phone')
    patient_id = serializers.ReadOnlyField(source='patient.patient_id')
    patient_gender = serializers.ReadOnlyField(source='patient.gender')
    patient_age = serializers.ReadOnlyField(source='patient.age')
    patient_address = serializers.ReadOnlyField(source='patient.address')
    patient_emergency_contact_name = serializers.ReadOnlyField(source='patient.emergency_contact_name')
    patient_emergency_contact_phone = serializers.ReadOnlyField(source='patient.emergency_contact_phone')
    visit_ticket = serializers.ReadOnlyField(source='visit.ticket_number')
    follow_up_date = DateOnlyField()
    reassigned_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = FollowUp
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'reassigned_at', 'completed_at')
