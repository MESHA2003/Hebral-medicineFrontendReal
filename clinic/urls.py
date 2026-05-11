from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PatientViewSet, VisitViewSet, MedicineViewSet, PrescriptionViewSet, StatsViewSet, FollowUpViewSet

router = DefaultRouter()
router.register('patients', PatientViewSet)
router.register('visits', VisitViewSet)
router.register('medicines', MedicineViewSet)
router.register('prescriptions', PrescriptionViewSet)
router.register('followups', FollowUpViewSet)
router.register('stats', StatsViewSet, basename='stats')

urlpatterns = [
    path('', include(router.urls)),
]
