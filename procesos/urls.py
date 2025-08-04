from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrganizacionViewSet, LoteViewSet, MuestraViewSet, EstadisticasView, crear_con_propietarios

router = DefaultRouter()
router.register(r'organizaciones', OrganizacionViewSet)
router.register(r'lotes', LoteViewSet)
router.register(r'muestras', MuestraViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('estadisticas/', EstadisticasView.as_view(), name='estadisticas'),
    path('lotes/crear-con-propietarios/', crear_con_propietarios, name='crear-con-propietarios'),
]