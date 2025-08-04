from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from . import views
from .views import (
    RegisterView, UserDetailView, OrganizacionListCreateView, OrganizacionDetailView,
    LoteCafeListCreateView, LoteCafeDetailView, MuestraCafeListView,
    crear_lote_con_propietarios, seleccionar_muestras, registrar_resultado_muestra,
    estadisticas_procesos, crear_segundo_muestreo, generar_reporte_separacion,
    actualizar_lote, CustomTokenObtainPairView,
    RegistroDescargaListCreateView, RegistroDescargaDetailView,
    InsumoListCreateView, InsumoDetailView, RegistroUsoMaquinariaListCreateView, 
    RegistroUsoMaquinariaDetailView, obtener_tipos_insumos, estadisticas_inventario, 
    actualizar_stock_insumo, PropietarioMaestroListCreateView, PropietarioMaestroDetailView,
    estadisticas_empleado, historial_actividades_empleado, procesar_separacion_colores,
    enviar_recepcion_final, procesar_limpieza, enviar_parte_limpia_limpieza,
    TareaInsumoListCreateView, TareaInsumoDetailView, ProcesoListCreateView, ProcesoDetailView,
    TareaProcesoListCreateView, TareaProcesoDetailView, avanzar_fase_proceso, finalizar_fase_proceso,
    estadisticas_procesos_produccion, lotes_disponibles_para_proceso,
    guardar_datos_pilado, guardar_datos_clasificacion, guardar_datos_densidad_1,
    guardar_datos_densidad_2, guardar_datos_color, guardar_datos_empaquetado
)

router = DefaultRouter()
router.register(r'bitacora', views.RegistroBitacoraViewSet, basename='bitacora')

urlpatterns = [
    # Autenticación
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('me/', UserDetailView.as_view(), name='user_info'),
    
    # Organizaciones
    path('organizaciones/', OrganizacionListCreateView.as_view(), name='organizacion-list-create'),
    path('organizaciones/<int:pk>/', OrganizacionDetailView.as_view(), name='organizacion-detail'),
    
    # Lotes de Café
    path('lotes/', LoteCafeListCreateView.as_view(), name='lote-list-create'),
    path('lotes/<int:pk>/', LoteCafeDetailView.as_view(), name='lote-detail'),
    path('lotes/crear-con-propietarios/', crear_lote_con_propietarios, name='crear-lote-propietarios'),
    path('lotes/<int:lote_id>/actualizar/', actualizar_lote, name='actualizar-lote'),
    path('lotes-disponibles-descarga/', views.lotes_disponibles_descarga, name='lotes_disponibles_descarga'),
    
    # Muestras
    path('muestras/', MuestraCafeListView.as_view(), name='muestra-list'),
    path('muestras/seleccionar/', seleccionar_muestras, name='seleccionar-muestras'),
    path('muestras/<int:muestra_id>/resultado/', registrar_resultado_muestra, name='resultado-muestra'),
    path('muestras/segundo-muestreo/', crear_segundo_muestreo, name='segundo-muestreo'),
    
    # Lotes - Reporte de separación
    path('lotes/<int:lote_id>/reporte-separacion/', generar_reporte_separacion, name='reporte-separacion'),
    
    # Procesos de separación inteligente
    path('lotes/<int:lote_id>/enviar-parte-limpia-limpieza/', enviar_parte_limpia_limpieza, name='enviar-parte-limpia-limpieza'),
    
    # Procesos de limpieza
    path('lotes/procesar-limpieza/', procesar_limpieza, name='procesar-limpieza'),
    
    # Procesos de separación por colores
    path('lotes/procesar-separacion-colores/', procesar_separacion_colores, name='procesar-separacion-colores'),
    path('lotes/enviar-recepcion-final/', enviar_recepcion_final, name='enviar-recepcion-final'),
    
    # Lotes para recepción final
    path('lotes/listos-recepcion-final/', views.lotes_listos_recepcion_final, name='lotes-listos-recepcion-final'),
    
    # Estadísticas generales
    path('estadisticas/', estadisticas_procesos, name='estadisticas-procesos'),

    # URLs para bitácora
    path('bitacora/estadisticas/', views.estadisticas_bitacora, name='bitacora-estadisticas'),
    path('bitacora/exportar-csv/', views.exportar_bitacora_csv, name='bitacora-exportar-csv'),

    # URLs para empleados - Descargas
    path('descargas/', RegistroDescargaListCreateView.as_view(), name='descarga-list-create'),
    path('descargas/<int:pk>/', RegistroDescargaDetailView.as_view(), name='descarga-detail'),
    
    # URLs para empleados - Insumos
    path('insumos/', InsumoListCreateView.as_view(), name='insumos-list-create'),
    path('insumos/<int:pk>/', InsumoDetailView.as_view(), name='insumos-detail'),
    path('tipos-insumos/', obtener_tipos_insumos, name='tipos-insumos'),
    path('inventario/estadisticas/', estadisticas_inventario, name='estadisticas-inventario'),
    path('insumos/<int:insumo_id>/actualizar-stock/', actualizar_stock_insumo, name='actualizar-stock-insumo'),
    
    # URLs para uso de maquinaria
    path('uso-maquinaria/', RegistroUsoMaquinariaListCreateView.as_view(), name='uso-maquinaria-list-create'),
    path('uso-maquinaria/<int:pk>/', RegistroUsoMaquinariaDetailView.as_view(), name='uso-maquinaria-detail'),
    
    # URLs para tareas con insumos
    path('tareas/', TareaInsumoListCreateView.as_view(), name='tareas-list-create'),
    path('tareas/<int:pk>/', TareaInsumoDetailView.as_view(), name='tareas-detail'),
    
    # URLs para propietarios maestros
    path('propietarios-maestros/', PropietarioMaestroListCreateView.as_view(), name='propietarios-maestros-list-create'),
    path('propietarios-maestros/<int:pk>/', PropietarioMaestroDetailView.as_view(), name='propietarios-maestros-detail'),
    path('propietarios-maestros/<int:propietario_id>/reactivar/', views.reactivar_propietario_maestro, name='reactivar-propietario-maestro'),
    path('propietarios-inactivos/', views.propietarios_inactivos, name='propietarios-inactivos'),
    path('buscar-propietario/<str:cedula>/', views.buscar_propietario_por_cedula, name='buscar_propietario_por_cedula'),
    
    # URLs para estadísticas e historial del empleado
    path('empleados/mis-estadisticas/', estadisticas_empleado, name='estadisticas-empleado'),
    path('empleados/mi-historial/', historial_actividades_empleado, name='historial-actividades-empleado'),
    
    # URLs para Procesos de Producción
    path('procesos/', ProcesoListCreateView.as_view(), name='procesos-list-create'),
    path('procesos/<int:pk>/', ProcesoDetailView.as_view(), name='procesos-detail'),
    path('procesos/<int:proceso_id>/avanzar-fase/', avanzar_fase_proceso, name='avanzar-fase-proceso'),
    path('procesos/<int:proceso_id>/finalizar-fase/', finalizar_fase_proceso, name='finalizar-fase-proceso'),
    path('procesos/estadisticas/', estadisticas_procesos_produccion, name='estadisticas-procesos-produccion'),
    path('procesos/lotes-disponibles/', lotes_disponibles_para_proceso, name='lotes-disponibles-proceso'),
    
    # URLs para Tareas de Proceso
    path('procesos/tareas/', TareaProcesoListCreateView.as_view(), name='tareas-proceso-list-create'),
    path('procesos/tareas/<int:pk>/', TareaProcesoDetailView.as_view(), name='tareas-proceso-detail'),
    
    # ✅ NUEVAS URLs PARA GUARDAR DATOS DE FORMULARIOS DE PROCESO
    path('procesos/<int:proceso_id>/guardar-pilado/', guardar_datos_pilado, name='guardar-datos-pilado'),
    path('procesos/<int:proceso_id>/guardar-clasificacion/', guardar_datos_clasificacion, name='guardar-datos-clasificacion'),
    path('procesos/<int:proceso_id>/guardar-densidad-1/', guardar_datos_densidad_1, name='guardar-datos-densidad-1'),
    path('procesos/<int:proceso_id>/guardar-densidad-2/', guardar_datos_densidad_2, name='guardar-datos-densidad-2'),
    path('procesos/<int:proceso_id>/guardar-color/', guardar_datos_color, name='guardar-datos-color'),
    path('procesos/<int:proceso_id>/guardar-empaquetado/', guardar_datos_empaquetado, name='guardar-datos-empaquetado'),
    
    # URLs del router
    path('', include(router.urls)),
]