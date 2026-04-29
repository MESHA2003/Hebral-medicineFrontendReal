from django.db.models import Sum, Count, F, Q
from datetime import timedelta
from django.utils import timezone

from accounts import models
from .models import Visit, Prescription, Medicine

def get_reception_stats():
    cutoff = timezone.now().date() - timedelta(days=30)
    visits = Visit.objects.filter(created_at__date__gte=cutoff)
    return {
        'total_visits': visits.count(),
        'waiting': visits.filter(status='waiting').count(),
        'in_progress': visits.filter(status='in_progress').count(),
        'completed': visits.filter(status='completed').count(),
        'dispensed': visits.filter(status='dispensed').count(),
        'today_registrations': visits.filter(created_at__date=timezone.now().date()).count(),
        'recent_visits': visits.order_by('-created_at')[:50],
    }

def get_doctor_stats():
    today = timezone.now().date()
    all_today = Visit.objects.filter(created_at__date=today)
    queue = Visit.objects.filter(status__in=['waiting', 'in_progress'])
    return {
        'waiting': queue.filter(status='waiting').count(),
        'in_progress': queue.filter(status='in_progress').count(),
        'completed_today': all_today.filter(status='completed').count(),
        'total_today': all_today.count(),
        'queue': queue.order_by('-created_at'),
    }

def get_pharmacy_stats():
    # Include both 'completed' (sent to pharmacy) and 'dispensed' (fully verified) visits
    completed_visits = Visit.objects.filter(status__in=['completed', 'dispensed'])
    prescriptions = Prescription.objects.filter(visit__in=completed_visits).select_related('medicine', 'visit__patient')
    pending = []
    fully = []
    total_units = 0
    for p in prescriptions:
        total_units += p.quantity_dispensed
        if p.quantity_dispensed < p.quantity_prescribed:
            pending.append(p)
        else:
            fully.append(p)
    # Sort fully dispensed by date descending
    fully_sorted = sorted(fully, key=lambda x: x.dispensed_at or x.updated_at, reverse=True)
    return {
        'pending_count': len(pending),
        'fully_dispensed_count': len(fully),
        'total_units_dispensed': total_units,
        'pending_prescriptions': pending,
        'fully_dispensed_prescriptions': fully_sorted,
    }

def get_admin_stats():
    cutoff = timezone.now().date() - timedelta(days=30)
    visits = Visit.objects.filter(created_at__date__gte=cutoff)
    medicines = Medicine.objects.all()
    prescriptions = Prescription.objects.filter(visit__in=visits)
    total_revenue = Visit.objects.filter(status='dispensed').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # Get top 5 most prescribed medicines in last 30 days
    top_medicines = prescriptions.values('medicine__name').annotate(count=Sum('quantity_prescribed')).order_by('-count')[:5]
    top_medicines_list = [{'name': m['medicine__name'], 'count': m['count']} for m in top_medicines]
    
    return {
        'patients_registered': visits.count(),
        'patients_treated': visits.filter(status='completed').count(),
        'medicines_dispensed': prescriptions.aggregate(Sum('quantity_dispensed'))['quantity_dispensed__sum'] or 0,
        'stock_alerts': medicines.filter(stock_quantity__lte=F('reorder_level')).count(),
        'total_revenue': total_revenue,
        'low_stock_medicines': medicines.filter(stock_quantity__lte=F('reorder_level')),
        'top_medicines': top_medicines_list,
    }