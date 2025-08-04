from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

class UserProfile(models.Model):
    ROLES_CHOICES = [
        ('EMPLEADO', 'Empleado'),
        ('ADMINISTRADOR', 'Administrador'),
        ('SECRETARIA', 'Secretaria'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    rol = models.CharField(max_length=20, choices=ROLES_CHOICES, default='EMPLEADO')
    telefono = models.CharField(max_length=20, blank=True)
    cedula = models.CharField(max_length=20, blank=True)
    departamento = models.CharField(max_length=100, blank=True)
    fecha_ingreso = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    foto_perfil = models.CharField(max_length=500, blank=True)
    
    class Meta:
        verbose_name_plural = "Perfiles de Usuario"
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_rol_display()}"
    
    @property
    def nombre_completo(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
    
    @property
    def puede_crear_lotes(self):
        return self.rol in ['ADMINISTRADOR', 'EMPLEADO']
    
    @property
    def puede_analizar_muestras(self):
        return self.rol in ['ADMINISTRADOR', 'EMPLEADO']
    
    @property
    def puede_generar_reportes(self):
        return self.rol in ['ADMINISTRADOR', 'SECRETARIA', 'EMPLEADO']
    
    @property
    def puede_administrar_usuarios(self):
        return self.rol == 'ADMINISTRADOR'
    
    @property
    def puede_ver_estadisticas_completas(self):
        return self.rol in ['ADMINISTRADOR', 'SECRETARIA']

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

class Organizacion(models.Model):
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=50, blank=True, null=True, help_text="Tipo de organización (Cooperativa, Asociación, etc.)")
    ruc = models.CharField(max_length=13, blank=True, null=True, help_text="RUC de la organización")
    mail = models.EmailField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    
    # Campos de ubicación/dirección
    provincia = models.CharField(max_length=100, blank=True, null=True, help_text="Provincia donde se ubica la organización")
    canton = models.CharField(max_length=100, blank=True, null=True, help_text="Cantón donde se ubica la organización")
    ciudad = models.CharField(max_length=100, blank=True, null=True, help_text="Ciudad donde se ubica la organización")
    plus_code = models.CharField(max_length=50, blank=True, null=True, help_text="Plus Code de Google Maps para ubicación exacta")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Organizaciones"
    
    def __str__(self):
        return self.nombre
    
    @property
    def ubicacion_completa(self):
        """Retorna la ubicación completa concatenada"""
        partes = []
        if self.ciudad:
            partes.append(self.ciudad)
        if self.canton:
            partes.append(self.canton)
        if self.provincia:
            partes.append(self.provincia)
        return ', '.join(partes) if partes else 'Sin ubicación especificada'

class LoteCafe(models.Model):
    ESTADOS_CHOICES = [
        ('PENDIENTE', 'Pendiente de análisis'),
        ('EN_PROCESO', 'En proceso de análisis'),
        ('APROBADO', 'Aprobado - Óptimas condiciones'),
        ('RECHAZADO', 'Rechazado - Con contaminación'),
        ('SEPARACION_PENDIENTE', 'Separación Pendiente - Requiere segundo muestreo'),
        ('SEPARACION_APLICADA', 'Separación Aplicada - Quintales contaminados separados'),
        ('LIMPIO', 'Limpio - Proceso de limpieza completado'),
        ('SEPARADO', 'Separado - Proceso de separación por colores completado'),
        ('FINALIZADO', 'Finalizado - Listo para comercialización'),
    ]
    
    organizacion = models.ForeignKey(Organizacion, on_delete=models.CASCADE)
    numero_lote = models.CharField(max_length=50, unique=True)
    fecha_entrega = models.DateTimeField()
    total_quintales = models.IntegerField()
    
    # Campos de peso para seguimiento del proceso
    peso_total_inicial = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Peso total del lote al ingreso en kilogramos")
    peso_total_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Peso total del lote después de todo el proceso en kilogramos")
    observaciones_peso = models.TextField(blank=True, help_text="Observaciones sobre el pesaje inicial")
    
    # Campos específicos para el proceso de limpieza
    fecha_limpieza = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora cuando se completó el proceso de limpieza")
    responsable_limpieza = models.CharField(max_length=200, blank=True, help_text="Nombre del responsable del proceso de limpieza")
    peso_impurezas = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Peso de las impurezas removidas en kilogramos")
    impurezas_encontradas = models.CharField(max_length=100, blank=True, help_text="Tipo de impurezas encontradas")
    tipo_limpieza = models.CharField(max_length=100, blank=True, help_text="Método de limpieza aplicado")
    duracion_limpieza = models.IntegerField(null=True, blank=True, help_text="Duración del proceso de limpieza en minutos")
    observaciones_limpieza = models.TextField(blank=True, help_text="Observaciones específicas del proceso de limpieza")
    
    # Campos específicos para el proceso de separación por colores
    fecha_separacion = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora cuando se completó el proceso de separación")
    responsable_separacion = models.CharField(max_length=200, blank=True, help_text="Nombre del responsable del proceso de separación")
    calidad_general = models.CharField(max_length=50, blank=True, help_text="Calidad general del café separado")
    duracion_separacion = models.IntegerField(null=True, blank=True, help_text="Duración del proceso de separación en minutos")
    clasificacion_colores = models.JSONField(default=dict, blank=True, help_text="Clasificación detallada por colores del café")
    observaciones_separacion = models.TextField(blank=True, help_text="Observaciones específicas del proceso de separación")
    
    # Campos específicos para la recepción final
    fecha_recepcion_final = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora de recepción final")
    responsable_recepcion_final = models.CharField(max_length=200, blank=True, help_text="Nombre del responsable de recepción final")
    calificacion_final = models.CharField(max_length=5, blank=True, help_text="Calificación final del lote (A, B, C, D)")
    observaciones_finales = models.TextField(blank=True, help_text="Observaciones finales del proceso completo")
    
    estado = models.CharField(max_length=20, choices=ESTADOS_CHOICES, default='PENDIENTE')
    observaciones = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    usuario_registro = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        verbose_name_plural = "Lotes de Café"
    
    def __str__(self):
        return f"Lote {self.numero_lote} - {self.organizacion.nombre}"
    
    @property
    def diferencia_peso(self):
        """Calcula la diferencia entre peso inicial y final"""
        if self.peso_total_inicial and self.peso_total_final:
            return self.peso_total_inicial - self.peso_total_final
        return None
    
    @property
    def porcentaje_perdida(self):
        """Calcula el porcentaje de pérdida de peso durante el proceso"""
        if self.peso_total_inicial and self.peso_total_final and self.peso_total_inicial > 0:
            diferencia = self.peso_total_inicial - self.peso_total_final
            return (diferencia / self.peso_total_inicial) * 100
        return None

class PropietarioMaestro(models.Model):
    """Modelo maestro para almacenar propietarios únicos que pueden ser reutilizados"""
    nombre_completo = models.CharField(max_length=200)
    cedula = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    
    # Campos de dirección específicos
    departamento = models.CharField(max_length=100, blank=True, help_text="Provincia")
    municipio = models.CharField(max_length=100, blank=True, help_text="Ciudad")
    comunidad = models.CharField(max_length=100, blank=True, help_text="Barrio/Comunidad")
    calle = models.CharField(max_length=200, blank=True, help_text="Calle/Finca")
    numero_casa = models.CharField(max_length=50, blank=True, help_text="Número de casa")
    referencias = models.CharField(max_length=300, blank=True, help_text="Referencias")
    
    # Campos de control
    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Propietario Maestro"
        verbose_name_plural = "Propietarios Maestros"
        ordering = ['nombre_completo']
    
    def __str__(self):
        return f"{self.nombre_completo} ({self.cedula})"
    
    @property
    def direccion_completa(self):
        """Retorna la dirección completa concatenada"""
        partes = []
        if self.departamento:
            partes.append(self.departamento)
        if self.municipio:
            partes.append(self.municipio)
        if self.comunidad:
            partes.append(self.comunidad)
        if self.calle:
            partes.append(self.calle)
        if self.numero_casa:
            partes.append(self.numero_casa)
        if self.referencias:
            partes.append(self.referencias)
        return ', '.join(partes) if partes else 'Sin dirección registrada'
    
    @property
    def total_entregas(self):
        """Retorna el número total de entregas realizadas por este propietario"""
        return self.entregas_cafe.count()
    
    @property
    def total_quintales_historicos(self):
        """Retorna el total de quintales entregados históricamente"""
        return self.entregas_cafe.aggregate(
            total=models.Sum('quintales_entregados')
        )['total'] or 0

class PropietarioCafe(models.Model):
    lote = models.ForeignKey(LoteCafe, on_delete=models.CASCADE, related_name='propietarios')
    propietario_maestro = models.ForeignKey(
        PropietarioMaestro, 
        on_delete=models.CASCADE, 
        related_name='entregas_cafe',
        null=True, blank=True,
        help_text="Referencia al propietario maestro"
    )
    quintales_entregados = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Campos de datos específicos para esta entrega (pueden diferir del maestro)
    nombre_completo = models.CharField(max_length=200, help_text="Copia del nombre al momento de la entrega")
    cedula = models.CharField(max_length=20, help_text="Copia de la cédula al momento de la entrega")
    telefono = models.CharField(max_length=20, blank=True, help_text="Teléfono al momento de la entrega")
    
    # Campos de dirección específicos para esta entrega
    departamento = models.CharField(max_length=100, blank=True)
    municipio = models.CharField(max_length=100, blank=True)
    comunidad = models.CharField(max_length=100, blank=True)
    calle = models.CharField(max_length=200, blank=True)
    numero_casa = models.CharField(max_length=50, blank=True)
    referencias = models.CharField(max_length=300, blank=True)
    
    # Mantener el campo direccion para compatibilidad
    direccion = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Propietarios de Café"
        unique_together = ['lote', 'cedula']
    
    def __str__(self):
        return f"{self.nombre_completo} - {self.quintales_entregados} quintales"
    
    def save(self, *args, **kwargs):
        # Copiar datos del propietario maestro si no están establecidos
        if self.propietario_maestro:
            if not self.nombre_completo:
                self.nombre_completo = self.propietario_maestro.nombre_completo
            if not self.cedula:
                self.cedula = self.propietario_maestro.cedula
            if not self.telefono:
                self.telefono = self.propietario_maestro.telefono
            if not self.departamento:
                self.departamento = self.propietario_maestro.departamento
            if not self.municipio:
                self.municipio = self.propietario_maestro.municipio
            if not self.comunidad:
                self.comunidad = self.propietario_maestro.comunidad
            if not self.calle:
                self.calle = self.propietario_maestro.calle
            if not self.numero_casa:
                self.numero_casa = self.propietario_maestro.numero_casa
            if not self.referencias:
                self.referencias = self.propietario_maestro.referencias
        super().save(*args, **kwargs)
    
    @property
    def direccion_completa(self):
        """Retorna la dirección completa concatenada"""
        partes = []
        if self.departamento:
            partes.append(self.departamento)
        if self.municipio:
            partes.append(self.municipio)
        if self.comunidad:
            partes.append(self.comunidad)
        if self.calle:
            partes.append(self.calle)
        if self.numero_casa:
            partes.append(self.numero_casa)
        if self.referencias:
            partes.append(self.referencias)
        return ', '.join(partes) if partes else self.direccion

class MuestraCafe(models.Model):
    ESTADOS_MUESTRA = [
        ('PENDIENTE', 'Pendiente de análisis'),
        ('ANALIZADA', 'Analizada'),
        ('CONTAMINADA', 'Contaminada'),
        ('APROBADA', 'Aprobada'),
    ]
    
    lote = models.ForeignKey(LoteCafe, on_delete=models.CASCADE, related_name='muestras')
    propietario = models.ForeignKey(PropietarioCafe, on_delete=models.CASCADE)
    numero_muestra = models.CharField(max_length=50)
    fecha_toma_muestra = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_MUESTRA, default='PENDIENTE')
    resultado_analisis = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    fecha_analisis = models.DateTimeField(null=True, blank=True)
    analista = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Nuevos campos para manejar muestreos múltiples
    es_segundo_muestreo = models.BooleanField(default=False)
    muestra_original = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='muestras_seguimiento')
    
    class Meta:
        verbose_name_plural = "Muestras de Café"
        unique_together = ['lote', 'numero_muestra']
    
    def __str__(self):
        return f"Muestra {self.numero_muestra} - {self.propietario.nombre_completo}"

class ProcesoAnalisis(models.Model):
    TIPOS_PROCESO = [
        ('INICIAL', 'Análisis inicial (5 muestras)'),
        ('SEGUIMIENTO', 'Análisis de seguimiento'),
        ('LIMPIEZA', 'Proceso de limpieza'),
        ('SEPARACION', 'Separación por colores'),
    ]
    
    lote = models.ForeignKey(LoteCafe, on_delete=models.CASCADE, related_name='procesos')
    tipo_proceso = models.CharField(max_length=20, choices=TIPOS_PROCESO)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    resultado_general = models.TextField(blank=True)
    aprobado = models.BooleanField(null=True, blank=True)
    usuario_proceso = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        verbose_name_plural = "Procesos de Análisis"
    
    def __str__(self):
        return f"Proceso {self.tipo_proceso} - Lote {self.lote.numero_lote}"

class RegistroBitacora(models.Model):
    ACCIONES_CHOICES = [
        ('CREAR_LOTE', 'Crear Lote'),
        ('ACTUALIZAR_LOTE', 'Actualizar Lote'),
        ('ELIMINAR_LOTE', 'Eliminar Lote'),
        ('TOMAR_MUESTRA', 'Tomar Muestra'),
        ('ANALIZAR_MUESTRA', 'Analizar Muestra'),
        ('ACTUALIZAR_MUESTRA', 'Actualizar Muestra'),
        ('SEGUNDO_MUESTREO', 'Segundo Muestreo'),
        ('GENERAR_REPORTE', 'Generar Reporte'),
        ('EXPORTAR_PDF', 'Exportar PDF'),
        ('EXPORTAR_CSV', 'Exportar CSV'),
        ('CONSULTAR_PERSONAL', 'Consultar Personal'),
        ('LOGIN', 'Inicio de Sesión'),
        ('LOGOUT', 'Cierre de Sesión'),
        ('CREAR_ORGANIZACION', 'Crear Organización'),
        ('ACTUALIZAR_ORGANIZACION', 'Actualizar Organización'),
        ('INICIAR_PROCESO', 'Iniciar Proceso'),
        ('FINALIZAR_PROCESO', 'Finalizar Proceso'),
        ('PROCESAR_LIMPIEZA', 'Procesar Limpieza'),
        ('SEPARACION_COLORES', 'Separación por Colores'),
        ('RECEPCION_FINAL', 'Recepción Final'),
        ('ENVIAR_LIMPIEZA_PARCIAL', 'Enviar Parte Limpia a Limpieza'),
        ('REGISTRAR_USO_MAQUINARIA', 'Registrar Uso de Maquinaria'),
    ]
    
    MODULOS_CHOICES = [
        ('RECEPCION', 'Recepción'),
        ('PROCESOS', 'Procesos'),
        ('PERSONAL', 'Personal'),
        ('REPORTES', 'Reportes'),
        ('SISTEMA', 'Sistema'),
        ('AUTENTICACION', 'Autenticación'),
        ('MAQUINARIA', 'Maquinaria'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=30, choices=ACCIONES_CHOICES)
    modulo = models.CharField(max_length=20, choices=MODULOS_CHOICES)
    descripcion = models.TextField()
    lote = models.ForeignKey(LoteCafe, on_delete=models.CASCADE, null=True, blank=True)
    muestra = models.ForeignKey(MuestraCafe, on_delete=models.CASCADE, null=True, blank=True)
    organizacion = models.ForeignKey(Organizacion, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    detalles_adicionales = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name_plural = "Registros de Bitácora"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.fecha.strftime('%Y-%m-%d %H:%M')} - {self.usuario.username} - {self.accion}"

    @classmethod
    def registrar_accion(cls, usuario, accion, modulo, descripcion, request=None, **kwargs):
        """
        Método de clase para registrar automáticamente acciones en la bitácora
        """
        ip_address = None
        user_agent = ''
        
        if request:
            # Obtener IP del request
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Obtener User Agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Crear el registro
        registro = cls.objects.create(
            usuario=usuario,
            accion=accion,
            modulo=modulo,
            descripcion=descripcion,
            ip_address=ip_address,
            user_agent=user_agent,
            lote=kwargs.get('lote'),
            muestra=kwargs.get('muestra'),
            organizacion=kwargs.get('organizacion'),
            detalles_adicionales=kwargs.get('detalles_adicionales', {})
        )
        
        return registro

class RegistroDescarga(models.Model):
    """Modelo para registrar las descargas de lotes realizadas directamente por empleados"""
    lote = models.ForeignKey(LoteCafe, on_delete=models.CASCADE, related_name='descargas')
    empleado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mis_descargas', help_text="Empleado que realizó la descarga")
    insumo = models.ForeignKey('Insumo', on_delete=models.CASCADE, related_name='descargas_realizadas', null=True, blank=True, help_text="Insumo utilizado en la descarga")
    cantidad_insumo_usado = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Cantidad del insumo utilizado")
    tiempo_uso_insumo = models.IntegerField(null=True, blank=True, help_text="Tiempo de uso del insumo en minutos")
    peso_descargado = models.DecimalField(max_digits=8, decimal_places=2, help_text="Peso en kilogramos")
    hora_inicio = models.DateTimeField(null=True, blank=True, help_text="Hora de inicio de la actividad de descarga")
    hora_fin = models.DateTimeField(null=True, blank=True, help_text="Hora de finalización de la actividad de descarga")
    tiempo_descarga_minutos = models.IntegerField(null=True, blank=True, help_text="Duración de la descarga en minutos")
    fecha_registro = models.DateTimeField(default=timezone.now, help_text="Fecha cuando se registró la descarga")
    observaciones = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Registro de Descarga"
        verbose_name_plural = "Registros de Descargas"
        ordering = ['-fecha_registro']
    
    def __str__(self):
        insumo_info = f" con {self.cantidad_insumo_usado} {self.insumo.get_unidad_medida_display()} de {self.insumo.nombre}" if self.insumo and self.cantidad_insumo_usado else ""
        tiempo_uso_info = f" durante {self.tiempo_uso_insumo} min" if self.tiempo_uso_insumo else ""
        return f"{self.empleado.get_full_name() or self.empleado.username} descargó {self.peso_descargado} kg{insumo_info}{tiempo_uso_info} - Lote {self.lote.numero_lote} ({self.tiempo_descarga_minutos} min)"
    
    def save(self, *args, **kwargs):
        # Calcular automáticamente el tiempo de descarga si no se proporciona
        if not self.tiempo_descarga_minutos and self.hora_inicio and self.hora_fin:
            diferencia = self.hora_fin - self.hora_inicio
            self.tiempo_descarga_minutos = int(diferencia.total_seconds() / 60)
        super().save(*args, **kwargs)

class Insumo(models.Model):
    """Modelo para definir los insumos disponibles (maquinaria, materiales, equipos, etc.)"""
    TIPOS_INSUMO = [
        ('MAQUINARIA', 'Maquinaria'),
        ('BALANZA', 'Balanza/Báscula'),
        ('CONTENEDOR', 'Contenedor/Saco/Bolsa'),
        ('HERRAMIENTA', 'Herramienta'),
        ('EQUIPO_MEDICION', 'Equipo de Medición'),
        ('MATERIAL_EMPAQUE', 'Material de Empaque'),
        ('EQUIPO_TRANSPORTE', 'Equipo de Transporte'),
        ('OTRO', 'Otro'),
    ]
    
    UNIDADES_MEDIDA = [
        ('UNIDAD', 'Unidad'),
        ('KG', 'Kilogramos'),
        ('LIBRA', 'Libras'),
        ('METRO', 'Metros'),
        ('LITRO', 'Litros'),
        ('SACO', 'Sacos'),
        ('CAJA', 'Cajas'),
        ('PAR', 'Par'),
    ]
    
    nombre = models.CharField(max_length=200, help_text="Nombre del insumo")
    tipo = models.CharField(max_length=50, choices=TIPOS_INSUMO, help_text="Tipo de insumo")
    codigo = models.CharField(max_length=50, unique=True, help_text="Código único del insumo")
    descripcion = models.TextField(blank=True, help_text="Descripción detallada del insumo")
    
    # Campos para inventario
    cantidad_disponible = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Cantidad disponible en inventario")
    cantidad_minima = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Cantidad mínima requerida (para alertas)")
    unidad_medida = models.CharField(max_length=20, choices=UNIDADES_MEDIDA, default='UNIDAD', help_text="Unidad de medida")
    
    # Campos específicos para maquinaria/equipos
    capacidad_maxima = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Capacidad máxima (para maquinaria/equipos)")
    modelo = models.CharField(max_length=100, blank=True, help_text="Modelo del insumo")
    marca = models.CharField(max_length=100, blank=True, help_text="Marca del insumo")
    
    # Campos de control
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_ultima_actualizacion = models.DateTimeField(auto_now=True)
    observaciones = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.codigo}) - {self.get_tipo_display()}"
    
    @property
    def necesita_reposicion(self):
        """Indica si el insumo necesita reposición"""
        return self.cantidad_disponible <= self.cantidad_minima
    
    @property
    def estado_inventario(self):
        """Retorna el estado del inventario"""
        if self.cantidad_disponible <= 0:
            return 'AGOTADO'
        elif self.cantidad_disponible <= self.cantidad_minima:
            return 'BAJO'
        else:
            return 'NORMAL'

class RegistroUsoMaquinaria(models.Model):
    """Modelo para registrar el uso de maquinaria realizado directamente por empleados"""
    TIPOS_MAQUINARIA = [
        ('MONTACARGAS', 'Montacargas'),
        ('GRUA', 'Grúa'),
        ('BANDA_TRANSPORTADORA', 'Banda Transportadora'),
        ('CARRETILLA', 'Carretilla'),
        ('OTRO', 'Otro'),
    ]
    
    empleado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mis_usos_maquinaria', help_text="Empleado que usó la maquinaria")
    maquinaria = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='registros_uso', null=True, blank=True)
    tipo_maquinaria = models.CharField(max_length=50, choices=TIPOS_MAQUINARIA, null=True, blank=True)
    lote = models.ForeignKey(LoteCafe, on_delete=models.CASCADE, related_name='usos_maquinaria')
    hora_inicio = models.DateTimeField()
    hora_fin = models.DateTimeField()
    tiempo_uso_minutos = models.IntegerField(help_text="Tiempo de uso en minutos")
    peso_total_descargado = models.DecimalField(max_digits=8, decimal_places=2, help_text="Peso total descargado con esta maquinaria en kg")
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Registro de Uso de Maquinaria"
        verbose_name_plural = "Registros de Uso de Maquinaria"
        ordering = ['-fecha_registro']
    
    def __str__(self):
        maquinaria_info = self.maquinaria.nombre if self.maquinaria else self.get_tipo_maquinaria_display()
        empleado_nombre = self.empleado.get_full_name() or self.empleado.username
        return f"{empleado_nombre} usó {maquinaria_info} - {self.tiempo_uso_minutos} min - {self.peso_total_descargado} kg"
    
    def get_tipo_maquinaria_display(self):
        """Retorna el nombre legible del tipo de maquinaria"""
        if self.tipo_maquinaria:
            return dict(self.TIPOS_MAQUINARIA).get(self.tipo_maquinaria, self.tipo_maquinaria)
        return "No especificado"
    
    def save(self, *args, **kwargs):
        # Calcular automáticamente el tiempo de uso si no se proporciona
        if not self.tiempo_uso_minutos and self.hora_inicio and self.hora_fin:
            diferencia = self.hora_fin - self.hora_inicio
            self.tiempo_uso_minutos = int(diferencia.total_seconds() / 60)
        super().save(*args, **kwargs)

# Nuevo modelo para registrar tareas de insumos utilizados
class TareaInsumo(models.Model):
    """Modelo para registrar tareas y el uso de insumos en procesos específicos"""
    muestra = models.ForeignKey(MuestraCafe, on_delete=models.CASCADE, related_name='tareas', null=True, blank=True)
    lote = models.ForeignKey(LoteCafe, on_delete=models.CASCADE, related_name='tareas', null=True, blank=True)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='tareas_uso')
    empleado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tareas_realizadas')
    
    # Información de la tarea
    descripcion = models.TextField(help_text="Descripción detallada de la tarea realizada")
    resultado_analisis = models.CharField(max_length=50, blank=True, help_text="Resultado del análisis o tipo de proceso realizado")
    
    # Información de tiempo
    hora_inicio = models.TimeField(null=True, blank=True, help_text="Hora de inicio de la tarea")
    hora_fin = models.TimeField(null=True, blank=True, help_text="Hora de finalización de la tarea")
    tiempo_uso = models.IntegerField(null=True, blank=True, help_text="Tiempo de uso del insumo en minutos")
    
    # Información de uso del insumo
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Cantidad del insumo utilizado")
    peso_usado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Peso del insumo usado en kg")
    
    # Campos de control
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Tarea con Insumo"
        verbose_name_plural = "Tareas con Insumos"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        empleado_nombre = self.empleado.get_full_name() or self.empleado.username
        muestra_info = f" - Muestra {self.muestra.numero_muestra}" if self.muestra else ""
        lote_info = f" - Lote {self.lote.numero_lote}" if self.lote else ""
        return f"{empleado_nombre}: {self.insumo.nombre}{muestra_info}{lote_info}"
    
    def save(self, *args, **kwargs):
        # Actualizar el stock del insumo si se especifica cantidad
        if self.cantidad and self.pk is None:  # Solo al crear, no al actualizar
            if self.insumo.cantidad_disponible >= self.cantidad:
                self.insumo.cantidad_disponible -= self.cantidad
                self.insumo.save()
        super().save(*args, **kwargs)

# Nuevo modelo para procesos de producción
class Proceso(models.Model):
    """Modelo para gestionar procesos de producción de café"""
    FASES_PROCESO = [
        ('PILADO', 'Pilado'),
        ('CLASIFICACION', 'Clasificación'),
        ('DENSIDAD', 'Densidad'),
        ('COLOR', 'Color'),
        ('EMPAQUE', 'Empaque'),
    ]
    
    ESTADOS_PROCESO = [
        ('INICIADO', 'Iniciado'),
        ('EN_PROCESO', 'En Proceso'),
        ('PAUSADO', 'Pausado'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    numero = models.CharField(max_length=50, unique=True, help_text="Número único del proceso (ej: Proceso001)")
    nombre = models.CharField(max_length=200, help_text="Nombre descriptivo del proceso")
    descripcion = models.TextField(blank=True, help_text="Descripción detallada del proceso")
    
    # Relación con lotes
    lotes = models.ManyToManyField(LoteCafe, related_name='procesos_produccion', help_text="Lotes incluidos en este proceso")
    
    # Estado y progreso
    estado = models.CharField(max_length=20, choices=ESTADOS_PROCESO, default='INICIADO')
    fase_actual = models.CharField(max_length=25, choices=FASES_PROCESO, default='PILADO')
    progreso = models.IntegerField(default=0, help_text="Progreso del proceso en porcentaje (0-100)")
    
    # Fechas y responsables
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin_estimada = models.DateTimeField(null=True, blank=True)
    fecha_fin_real = models.DateTimeField(null=True, blank=True)
    responsable = models.ForeignKey(User, on_delete=models.CASCADE, related_name='procesos_responsable')
    usuario_creacion = models.ForeignKey(User, on_delete=models.CASCADE, related_name='procesos_creados')
    
    # Información técnica
    peso_total_inicial = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Peso total inicial en kg")
    peso_total_actual = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Peso actual del proceso en kg")
    quintales_totales = models.IntegerField(default=0, help_text="Total de quintales en el proceso")
    
    # Observaciones y notas
    observaciones = models.TextField(blank=True)
    notas_tecnicas = models.JSONField(default=dict, blank=True, help_text="Notas técnicas de cada fase")
    
    # ✅ NUEVOS CAMPOS PARA ALMACENAR DATOS DETALLADOS DE CADA FASE
    # Datos específicos del pilado
    datos_pilado = models.JSONField(default=dict, blank=True, help_text="Datos detallados del proceso de pilado")
    
    # Datos específicos de clasificación
    datos_clasificacion = models.JSONField(default=dict, blank=True, help_text="Datos detallados del proceso de clasificación")
    
    # Datos específicos de densidad (primera parte)
    datos_densidad_1 = models.JSONField(default=dict, blank=True, help_text="Datos de la primera parte del proceso de densidad")
    
    # Datos específicos de densidad (segunda parte - densimetría 2)
    datos_densidad_2 = models.JSONField(default=dict, blank=True, help_text="Datos de la segunda parte del proceso de densidad (densimetría 2)")
    
    # Datos específicos de separación por color
    datos_color = models.JSONField(default=dict, blank=True, help_text="Datos detallados del proceso de separación por color")
    
    # Datos específicos de empaquetado
    datos_empaquetado = models.JSONField(default=dict, blank=True, help_text="Datos detallados del proceso de empaquetado")
    
    # Campos de control
    activo = models.BooleanField(default=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Proceso de Producción"
        verbose_name_plural = "Procesos de Producción"
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"{self.numero} - {self.nombre}"
    
    @property
    def total_lotes(self):
        """Retorna el número total de lotes en el proceso"""
        return self.lotes.count()
    
    @property
    def porcentaje_progreso(self):
        """Calcula el porcentaje de progreso basado en la fase actual"""
        fases_progreso = {
            'PILADO': 16,
            'CLASIFICACION': 33,
            'DENSIDAD': 50,
            'COLOR': 66,
            'EMPAQUE': 100
        }
        return fases_progreso.get(self.fase_actual, 0)
    
    @property
    def duracion_dias(self):
        """Calcula la duración en días desde el inicio"""
        if self.fecha_fin_real:
            return (self.fecha_fin_real - self.fecha_inicio).days
        else:
            from django.utils import timezone
            return (timezone.now() - self.fecha_inicio).days
    
    def avanzar_fase(self):
        """Avanza a la siguiente fase del proceso"""
        fases = ['PILADO', 'CLASIFICACION', 'DENSIDAD', 'COLOR', 'EMPAQUE']
        try:
            indice_actual = fases.index(self.fase_actual)
            if indice_actual < len(fases) - 1:
                self.fase_actual = fases[indice_actual + 1]
                self.progreso = self.porcentaje_progreso
                if self.fase_actual == 'EMPAQUE':
                    self.estado = 'COMPLETADO'
                    self.fecha_fin_real = timezone.now()
                self.save()
                return True
        except ValueError:
            pass
        return False
    
    def calcular_totales(self):
        """Calcula los totales de peso y quintales basado en los lotes"""
        lotes = self.lotes.all()
        if lotes:
            self.quintales_totales = sum(lote.total_quintales for lote in lotes)
            peso_inicial = sum(lote.peso_total_inicial or 0 for lote in lotes)
            peso_actual = sum(lote.peso_total_final or lote.peso_total_inicial or 0 for lote in lotes)
            self.peso_total_inicial = peso_inicial if peso_inicial > 0 else None
            self.peso_total_actual = peso_actual if peso_actual > 0 else None
            self.save()
    
    def agregar_nota_tecnica(self, fase, nota):
        """Agrega una nota técnica para una fase específica"""
        if not self.notas_tecnicas:
            self.notas_tecnicas = {}
        
        if fase not in self.notas_tecnicas:
            self.notas_tecnicas[fase] = []
        
        from django.utils import timezone
        self.notas_tecnicas[fase].append({
            'fecha': timezone.now().isoformat(),
            'nota': nota
        })
        self.save()


class TareaProceso(models.Model):
    """Modelo para registrar tareas específicas dentro de un proceso"""
    TIPOS_TAREA = [
        ('PILADO_CANTEADO', 'Pilado - Canteado'),
        ('PILADO_REPOSO', 'Pilado - Tiempo de Reposo'),
        ('CLASIFICACION_INICIO', 'Clasificación - Inicio'),
        ('CLASIFICACION_CONTROL', 'Clasificación - Control'),
        ('DENSIDAD_INICIO', 'Densidad - Inicio'),
        ('DENSIDAD_CONTROL', 'Densidad - Control'),
        ('COLOR_INICIO', 'Color - Inicio'),
        ('COLOR_CONTROL', 'Color - Control'),
        ('EMPAQUE_PREPARACION', 'Empaque - Preparación'),
        ('EMPAQUE_PROCESO', 'Empaque - Proceso'),
        ('OTRO', 'Otra Tarea'),
    ]
    
    proceso = models.ForeignKey(Proceso, on_delete=models.CASCADE, related_name='tareas')
    tipo_tarea = models.CharField(max_length=30, choices=TIPOS_TAREA)
    descripcion = models.TextField(help_text="Descripción detallada de la tarea")
    fase = models.CharField(max_length=25, choices=Proceso.FASES_PROCESO)
    
    # Información de tiempo
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    duracion_minutos = models.IntegerField(null=True, blank=True)
    
    # Información técnica
    peso_impurezas_encontradas = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    peso_impurezas_removidas = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Trabajador y fecha
    empleado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tareas_proceso')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_ejecucion = models.DateField(null=True, blank=True)
    
    # Opciones específicas
    canteado_realizado = models.BooleanField(default=False)
    tiempo_reposo_interno = models.BooleanField(default=False)
    
    # Observaciones
    observaciones = models.TextField(blank=True)
    resultado = models.TextField(blank=True, help_text="Resultado o conclusión de la tarea")
    
    # Control
    completada = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Tarea de Proceso"
        verbose_name_plural = "Tareas de Procesos"
        ordering = ['-fecha_registro']
    
    def __str__(self):
        return f"{self.proceso.numero} - {self.get_tipo_tarea_display()}"
    
    def calcular_duracion(self):
        """Calcula la duración en minutos si se proporcionan hora inicio y fin"""
        if self.hora_inicio and self.hora_fin:
            from datetime import datetime, timedelta
            inicio = datetime.combine(datetime.today(), self.hora_inicio)
            fin = datetime.combine(datetime.today(), self.hora_fin)
            if fin < inicio:  # Si cruza medianoche
                fin += timedelta(days=1)
            diferencia = fin - inicio
            self.duracion_minutos = int(diferencia.total_seconds() / 60)
            self.save()
