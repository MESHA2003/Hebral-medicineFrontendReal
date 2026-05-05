from django.db.models import Sum, Count, F
from datetime import timedelta
from django.utils import timezone

def get_reception_stats():
    from .models import Visit
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
    from .models import Visit
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
    from .models import Visit, Prescription
    completed_visits = Visit.objects.filter(status__in=['completed', 'dispensed'])
    
    # Separate into pending (still has undispensed items) and fully dispensed
    pending_visits = []
    dispensed_visits = []
    total_units = 0
    
    for visit in completed_visits:
        prescriptions = visit.prescriptions.all()
        has_pending = any(p.quantity_dispensed < p.quantity_prescribed for p in prescriptions)
        for p in prescriptions:
            total_units += p.quantity_dispensed
        if has_pending:
            pending_visits.append(visit)
        else:
            dispensed_visits.append(visit)
    
    dispensed_visits_sorted = sorted(dispensed_visits, key=lambda v: v.updated_at, reverse=True)
    
    return {
        'pending_count': len(pending_visits),
        'fully_dispensed_count': len(dispensed_visits),
        'total_units_dispensed': total_units,
        'pending_visits': pending_visits,
        'dispensed_visits': dispensed_visits_sorted,
    }

def get_admin_stats():
    from .models import Visit, Medicine, Prescription
    cutoff = timezone.now().date() - timedelta(days=30)
    visits = Visit.objects.filter(created_at__date__gte=cutoff)
    medicines = Medicine.objects.all()
    prescriptions = Prescription.objects.filter(visit__in=visits)
    total_revenue = Visit.objects.filter(status='dispensed').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
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