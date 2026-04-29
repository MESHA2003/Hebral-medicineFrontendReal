from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Patient, Visit, Medicine, Prescription

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('patient_id', 'name', 'phone', 'age', 'gender', 'created_at')
    search_fields = ('patient_id', 'name', 'phone')
    readonly_fields = ('patient_id',)

@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'patient', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'stock_quantity', 'reorder_level', 'critical_level')

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('visit', 'medicine', 'quantity_prescribed', 'quantity_dispensed')