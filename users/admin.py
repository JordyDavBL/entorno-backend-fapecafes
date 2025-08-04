from django.contrib import admin
from .models import Organizacion, LoteCafe, PropietarioCafe, MuestraCafe, ProcesoAnalisis, RegistroBitacora, RegistroDescarga, Insumo, RegistroUsoMaquinaria, Proceso, TareaProceso

@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'mail', 'telefono', 'fecha_creacion']
    search_fields = ['nombre', 'mail']
    list_filter = ['fecha_creacion']

@admin.register(LoteCafe)
class LoteCafeAdmin(admin.ModelAdmin):
    list_display = ['numero_lote', 'organizacion', 'total_quintales', 'estado', 'fecha_entrega', 'usuario_registro']
    list_filter = ['estado', 'fecha_entrega', 'organizacion']
    search_fields = ['numero_lote', 'organizacion__nombre']
    readonly_fields = ['fecha_creacion']

@admin.register(PropietarioCafe)
class PropietarioCafeAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'cedula', 'lote', 'quintales_entregados']
    list_filter = ['lote__organizacion', 'lote']
    search_fields = ['nombre_completo', 'cedula', 'lote__numero_lote']

@admin.register(MuestraCafe)
class MuestraCafeAdmin(admin.ModelAdmin):
    list_display = ['numero_muestra', 'propietario', 'lote', 'estado', 'fecha_toma_muestra', 'analista']
    list_filter = ['estado', 'fecha_toma_muestra', 'lote__organizacion']
    search_fields = ['numero_muestra', 'propietario__nombre_completo', 'lote__numero_lote']
    readonly_fields = ['fecha_toma_muestra']

@admin.register(ProcesoAnalisis)
class ProcesoAnalisisAdmin(admin.ModelAdmin):
    list_display = ['lote', 'tipo_proceso', 'fecha_inicio', 'fecha_finalizacion', 'aprobado', 'usuario_proceso']
    list_filter = ['tipo_proceso', 'aprobado', 'fecha_inicio']
    search_fields = ['lote__numero_lote']
    readonly_fields = ['fecha_inicio']

@admin.register(RegistroBitacora)
class RegistroBitacoraAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'usuario', 'accion', 'modulo', 'descripcion_corta', 'ip_address']
    list_filter = ['accion', 'modulo', 'fecha', 'usuario']
    search_fields = ['usuario__username', 'descripcion', 'ip_address']
    readonly_fields = ['fecha', 'ip_address', 'user_agent']
    ordering = ['-fecha']
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

@admin.register(RegistroDescarga)
class RegistroDescargaAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'lote', 'peso_descargado', 'fecha_registro', 'tiempo_descarga_minutos']
    list_filter = ['fecha_registro', 'lote__organizacion', 'empleado']
    search_fields = ['empleado__username', 'empleado__first_name', 'empleado__last_name', 'lote__numero_lote']
    readonly_fields = ['fecha_registro', 'tiempo_descarga_minutos']
    ordering = ['-fecha_registro']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('empleado', 'lote', 'lote__organizacion')

@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'tipo', 'cantidad_disponible', 'unidad_medida', 'estado_inventario', 'activo', 'fecha_creacion']
    list_filter = ['tipo', 'activo', 'unidad_medida', 'fecha_creacion']
    search_fields = ['nombre', 'codigo', 'descripcion', 'marca', 'modelo']
    readonly_fields = ['fecha_creacion', 'fecha_ultima_actualizacion', 'estado_inventario']
    ordering = ['nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'codigo', 'tipo', 'descripcion', 'activo')
        }),
        ('Inventario', {
            'fields': ('cantidad_disponible', 'cantidad_minima', 'unidad_medida')
        }),
        ('Detalles Técnicos', {
            'fields': ('capacidad_maxima', 'marca', 'modelo'),
            'classes': ('collapse',)
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
        ('Información del Sistema', {
            'fields': ('fecha_creacion', 'fecha_ultima_actualizacion', 'estado_inventario'),
            'classes': ('collapse',)
        })
    )
    
    def estado_inventario(self, obj):
        estado = obj.estado_inventario
        colores = {
            'NORMAL': 'green',
            'BAJO': 'orange', 
            'AGOTADO': 'red'
        }
        return f'<span style="color: {colores.get(estado, "black")}; font-weight: bold;">{estado}</span>'
    estado_inventario.allow_tags = True
    estado_inventario.short_description = 'Estado del Inventario'

@admin.register(RegistroUsoMaquinaria)
class RegistroUsoMaquinariaAdmin(admin.ModelAdmin):
    list_display = ['empleado', 'insumo_usado', 'lote', 'hora_inicio', 'hora_fin', 'tiempo_uso_minutos', 'peso_total_descargado']
    list_filter = ['fecha_registro', 'tipo_maquinaria', 'empleado']
    search_fields = ['empleado__username', 'maquinaria__nombre', 'lote__numero_lote']
    readonly_fields = ['fecha_registro', 'tiempo_uso_minutos']
    ordering = ['-fecha_registro']
    
    def insumo_usado(self, obj):
        if obj.maquinaria:
            return f"{obj.maquinaria.nombre} ({obj.maquinaria.codigo})"
        return obj.get_tipo_maquinaria_display()
    insumo_usado.short_description = 'Insumo/Maquinaria'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('empleado', 'maquinaria', 'lote')

@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nombre', 'estado', 'fase_actual', 'progreso', 'responsable', 'fecha_inicio', 'total_lotes']
    list_filter = ['estado', 'fase_actual', 'responsable', 'fecha_inicio', 'activo']
    search_fields = ['numero', 'nombre', 'descripcion', 'responsable__username', 'responsable__first_name', 'responsable__last_name']
    readonly_fields = ['numero', 'fecha_inicio', 'fecha_actualizacion', 'usuario_creacion', 'total_lotes', 'porcentaje_progreso', 'duracion_dias']
    ordering = ['-fecha_inicio']
    filter_horizontal = ['lotes']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('numero', 'nombre', 'descripcion', 'activo')
        }),
        ('Estado y Progreso', {
            'fields': ('estado', 'fase_actual', 'progreso', 'porcentaje_progreso')
        }),
        ('Responsables y Fechas', {
            'fields': ('responsable', 'usuario_creacion', 'fecha_inicio', 'fecha_fin_estimada', 'fecha_fin_real', 'fecha_actualizacion', 'duracion_dias')
        }),
        ('Información Técnica', {
            'fields': ('peso_total_inicial', 'peso_total_actual', 'quintales_totales', 'total_lotes'),
            'classes': ('collapse',)
        }),
        ('Lotes Incluidos', {
            'fields': ('lotes',),
        }),
        ('Observaciones y Notas', {
            'fields': ('observaciones', 'notas_tecnicas'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('responsable', 'usuario_creacion').prefetch_related('lotes')

@admin.register(TareaProceso)
class TareaProcesoAdmin(admin.ModelAdmin):
    list_display = ['proceso', 'tipo_tarea', 'fase', 'empleado', 'fecha_registro', 'completada', 'duracion_minutos']
    list_filter = ['tipo_tarea', 'fase', 'completada', 'fecha_registro', 'empleado']
    search_fields = ['proceso__numero', 'descripcion', 'empleado__username', 'empleado__first_name', 'empleado__last_name']
    readonly_fields = ['fecha_registro', 'duracion_minutos']
    ordering = ['-fecha_registro']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('proceso', 'tipo_tarea', 'fase', 'descripcion', 'completada')
        }),
        ('Empleado y Fechas', {
            'fields': ('empleado', 'fecha_registro', 'fecha_ejecucion')
        }),
        ('Tiempo de Ejecución', {
            'fields': ('hora_inicio', 'hora_fin', 'duracion_minutos'),
            'classes': ('collapse',)
        }),
        ('Información Técnica', {
            'fields': ('peso_impurezas_encontradas', 'peso_impurezas_removidas', 'canteado_realizado', 'tiempo_reposo_interno'),
            'classes': ('collapse',)
        }),
        ('Resultados y Observaciones', {
            'fields': ('resultado', 'observaciones'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('proceso', 'empleado')
