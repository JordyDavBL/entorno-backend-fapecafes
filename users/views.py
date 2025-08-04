from django.shortcuts import render
from rest_framework import generics, permissions, status, viewsets, filters
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Sum, Q, F
from django.db import models
from datetime import timedelta
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import (RegisterSerializer, UserSerializer, OrganizacionSerializer,
                         LoteCafeSerializer, PropietarioCafeSerializer, MuestraCafeSerializer,
                         ProcesoAnalisisSerializer, CrearLoteConPropietariosSerializer,
                         SeleccionarMuestrasSerializer, RegistroBitacoraSerializer,
                         RegistroDescargaSerializer, InsumoSerializer, RegistroUsoMaquinariaSerializer,
                         PropietarioMaestroSerializer, TareaInsumoSerializer, ProcesoSerializer,
                         TareaProcesoSerializer)
from .models import (Organizacion, LoteCafe, PropietarioCafe, MuestraCafe, ProcesoAnalisis, 
                    RegistroBitacora, RegistroDescarga, Insumo, RegistroUsoMaquinaria,
                    PropietarioMaestro, TareaInsumo, Proceso, TareaProceso)

# Create your views here.

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer
    
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            # Registrar acción en bitácora si es posible
            try:
                from .models import RegistroBitacora
                RegistroBitacora.registrar_accion(
                    usuario=user,
                    accion='REGISTRO',
                    modulo='AUTENTICACION',
                    descripcion=f'Usuario registrado: {user.username}',
                    request=request
                )
            except Exception:
                # Si falla el registro en bitácora, continuar sin detener el registro
                pass
            
            return Response({
                'mensaje': 'Usuario registrado exitosamente',
                'usuario': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Error en el registro: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserDetailView(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer
    
    def get_object(self):
        return self.request.user

# Vistas para Organizaciones
class OrganizacionListCreateView(generics.ListCreateAPIView):
    queryset = Organizacion.objects.all()
    serializer_class = OrganizacionSerializer
    permission_classes = [permissions.IsAuthenticated]

class OrganizacionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Organizacion.objects.all()
    serializer_class = OrganizacionSerializer
    permission_classes = [permissions.IsAuthenticated]

# Vistas para Lotes de Café
class LoteCafeListCreateView(generics.ListCreateAPIView):
    queryset = LoteCafe.objects.all().order_by('-fecha_creacion')
    serializer_class = LoteCafeSerializer
    permission_classes = [permissions.IsAuthenticated]

class LoteCafeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LoteCafe.objects.all()
    serializer_class = LoteCafeSerializer
    permission_classes = [permissions.IsAuthenticated]

# Vista para crear lote con propietarios
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def crear_lote_con_propietarios(request):
    serializer = CrearLoteConPropietariosSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        lote = serializer.save()
        
        # Registrar acción en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='CREAR_LOTE',
            modulo='RECEPCION',
            descripcion=f'Lote creado: {lote.numero_lote} - Organización: {lote.organizacion.nombre} - {len(lote.propietarios.all())} propietarios',
            request=request,
            lote=lote,
            organizacion=lote.organizacion
        )
        
        return Response(LoteCafeSerializer(lote).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Vista para seleccionar muestras de un lote
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def seleccionar_muestras(request):
    serializer = SeleccionarMuestrasSerializer(data=request.data)
    if serializer.is_valid():
        lote_id = serializer.validated_data['lote_id']
        propietarios_ids = serializer.validated_data['propietarios_seleccionados']
        
        try:
            lote = LoteCafe.objects.get(id=lote_id)
            propietarios = PropietarioCafe.objects.filter(
                lote=lote, 
                id__in=propietarios_ids
            )
            
            if len(propietarios) != len(propietarios_ids):
                return Response({'error': 'Algunos propietarios no son válidos'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Crear muestras para los propietarios seleccionados
            muestras_creadas = []
            for i, propietario in enumerate(propietarios, 1):
                muestra = MuestraCafe.objects.create(
                    lote=lote,
                    propietario=propietario,
                    numero_muestra=f"{lote.numero_lote}-M{i:02d}",
                    analista=request.user
                )
                muestras_creadas.append(muestra)
            
            # Actualizar estado del lote
            lote.estado = 'EN_PROCESO'
            lote.save()
            
            # Registrar acción en bitácora
            RegistroBitacora.registrar_accion(
                usuario=request.user,
                accion='TOMAR_MUESTRA',
                modulo='PROCESOS',
                descripcion=f'Se tomaron {len(muestras_creadas)} muestras del lote {lote.numero_lote}',
                request=request,
                lote=lote,
                detalles_adicionales={
                    'propietarios_seleccionados': [p.nombre_completo for p in propietarios],
                    'numero_muestras': len(muestras_creadas)
                }
            )
            
            return Response({
                'mensaje': f'Se crearon {len(muestras_creadas)} muestras exitosamente',
                'muestras': MuestraCafeSerializer(muestras_creadas, many=True).data
            }, status=status.HTTP_201_CREATED)
            
        except LoteCafe.DoesNotExist:
            return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Vista para registrar resultados de análisis
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def registrar_resultado_muestra(request, muestra_id):
    try:
        muestra = MuestraCafe.objects.get(id=muestra_id)
        
        estado = request.data.get('estado')
        resultado_analisis = request.data.get('resultado_analisis', '')
        observaciones = request.data.get('observaciones', '')
        
        if estado not in ['APROBADA', 'CONTAMINADA']:
            return Response({'error': 'Estado inválido'}, status=status.HTTP_400_BAD_REQUEST)
        
        muestra.estado = estado
        muestra.resultado_analisis = resultado_analisis
        muestra.observaciones = observaciones
        muestra.fecha_analisis = timezone.now()
        muestra.save()
        
        # Registrar análisis en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='ANALIZAR_MUESTRA',
            modulo='PROCESOS',
            descripcion=f'Análisis registrado para muestra {muestra.numero_muestra}: {estado} - {resultado_analisis[:100]}...' if len(resultado_analisis) > 100 else f'Análisis registrado para muestra {muestra.numero_muestra}: {estado} - {resultado_analisis}',
            request=request,
            lote=muestra.lote,
            muestra=muestra,
            detalles_adicionales={
                'estado_anterior': 'PENDIENTE',
                'estado_nuevo': estado,
                'propietario': muestra.propietario.nombre_completo,
                'es_segundo_muestreo': muestra.es_segundo_muestreo
            }
        )
        
        # ✅ CORRECCIÓN PRINCIPAL: Verificar si la muestra actual ya es un segundo muestreo
        if muestra.es_segundo_muestreo and estado == 'CONTAMINADA':
            # Esta es una muestra de segundo muestreo que sale contaminada
            # No debe crear otro segundo muestreo, debe proceder con separación
            response_data = {
                'mensaje': 'Segundo muestreo completado. La muestra está confirmada como contaminada.',
                'muestra': MuestraCafeSerializer(muestra).data,
                'lote_estado': muestra.lote.estado,
                'requiere_segundo_muestreo': False,
                'separacion_definitiva': True,
                'es_segundo_muestreo_contaminado': True,
                'mensaje_separacion': f'El propietario {muestra.propietario.nombre_completo} debe ser separado definitivamente del lote. La contaminación se ha confirmado en el segundo análisis.'
            }
            
            # Actualizar estado del lote si es necesario
            lote = muestra.lote
            # Verificar si todas las muestras de segundo muestreo están completas
            muestras_segundo = lote.muestras.filter(es_segundo_muestreo=True)
            muestras_segundo_pendientes = muestras_segundo.filter(estado='PENDIENTE').count()
            
            if muestras_segundo_pendientes == 0:
                # Todas las muestras de segundo muestreo están completas, aplicar separación final
                muestras_iniciales = lote.muestras.filter(es_segundo_muestreo=False)
                muestras_segundo_contaminadas = muestras_segundo.filter(estado='CONTAMINADA')
                muestras_segundo_aprobadas = muestras_segundo.filter(estado='APROBADA')
                muestras_iniciales_aprobadas = muestras_iniciales.filter(estado='APROBADA')
                
                # ✅ CALCULAR QUINTALES REALES DESPUÉS DE SEPARACIÓN
                quintales_originales = lote.total_quintales
                quintales_finales_contaminados = sum(m.propietario.quintales_entregados for m in muestras_segundo_contaminadas)
                quintales_finales_aprobados = sum(m.propietario.quintales_entregados for m in muestras_iniciales_aprobadas) + sum(m.propietario.quintales_entregados for m in muestras_segundo_aprobadas)
                
                propietarios_definitivamente_contaminados = [m.propietario.nombre_completo for m in muestras_segundo_contaminadas]
                propietarios_recuperados_segundo_muestreo = [m.propietario.nombre_completo for m in muestras_segundo_aprobadas]
                
                if muestras_segundo_contaminadas.exists():
                    # ✅ ACTUALIZAR FÍSICAMENTE LOS QUINTALES DEL LOTE
                    lote.total_quintales = quintales_finales_aprobados
                    
                    # Ajustar peso proporcionalmente si existe
                    if lote.peso_total_inicial and quintales_originales > 0:
                        from decimal import Decimal
                        proporcion_limpia = Decimal(str(quintales_finales_aprobados)) / Decimal(str(quintales_originales))
                        lote.peso_total_inicial = lote.peso_total_inicial * proporcion_limpia
                    
                    if lote.peso_total_final and quintales_originales > 0:
                        from decimal import Decimal
                        proporcion_limpia = Decimal(str(quintales_finales_aprobados)) / Decimal(str(quintales_originales))
                        lote.peso_total_final = lote.peso_total_final * proporcion_limpia
                    
                    # Aplicar separación inteligente
                    lote.estado = 'SEPARACION_APLICADA'
                    lote.observaciones = f"""SEPARACIÓN INTELIGENTE APLICADA - SEGUNDO MUESTREO COMPLETADO
                    
Resultado final del análisis:
- Total propietarios original: {lote.propietarios.count()}
- Muestras iniciales: {muestras_iniciales.count()}
- Segundo muestreo: {muestras_segundo.count()}

SEPARACIÓN REALIZADA:
✅ QUINTALES CONSERVADOS: {quintales_finales_aprobados} qq
   - Propietarios aprobados desde inicio: {', '.join([m.propietario.nombre_completo for m in muestras_iniciales_aprobadas])}
   {"- Propietarios recuperados en 2do muestreo: " + ', '.join(propietarios_recuperados_segundo_muestreo) if propietarios_recuperados_segundo_muestreo else ""}

❌ QUINTALES SEPARADOS: {quintales_finales_contaminados} qq  
   - Propietarios con contaminación confirmada: {', '.join(propietarios_definitivamente_contaminados)}

RESUMEN:
- Quintales originales: {quintales_originales} qq
- El {round((quintales_finales_aprobados/quintales_originales)*100, 1)}% del lote ({quintales_finales_aprobados} qq) se conserva para continuar el proceso
- El {round((quintales_finales_contaminados/quintales_originales)*100, 1)}% del lote ({quintales_finales_contaminados} qq) se separa por contaminación confirmada

RESULTADO: SEPARACIÓN EXITOSA - El lote principal puede continuar el proceso de producción con {quintales_finales_aprobados} quintales."""
                    
                    response_data['mensaje'] = f'Segundo muestreo completado. Se separaron {quintales_finales_contaminados} quintales contaminados. {quintales_finales_aprobados} quintales continúan en el proceso.'
                else:
                    # Todos aprobados en segundo muestreo - mantener quintales originales
                    lote.estado = 'APROBADO'
                    lote.observaciones = f"""LOTE COMPLETAMENTE RECUPERADO - SEGUNDO MUESTREO EXITOSO
                    
Resultado excepcional:
- Todas las muestras de segundo muestreo: APROBADAS ✅
- El 100% del lote ({lote.total_quintales} quintales) ha sido aprobado
- No se requiere separación de quintales

RESULTADO: LOTE COMPLETAMENTE APROBADO - Café en óptimas condiciones para continuar producción."""
                    
                    response_data['mensaje'] = '¡Excelente! Segundo muestreo exitoso. Toda la contaminación inicial se ha resuelto. El lote completo puede continuar.'
                
                # Finalizar procesos abiertos
                procesos_abiertos = lote.procesos.filter(fecha_finalizacion__isnull=True)
                for proceso in procesos_abiertos:
                    proceso.fecha_finalizacion = timezone.now()
                    proceso.aprobado = (lote.estado in ['APROBADO', 'SEPARACION_APLICADA'])
                    proceso.resultado_general = lote.observaciones
                    proceso.save()
                
                lote.save()
            
            response_data['lote_estado'] = muestra.lote.estado
            return Response(response_data)
        
        # ✅ LÓGICA ORIGINAL PARA PRIMER MUESTREO
        # Verificar si todas las muestras del lote han sido analizadas
        lote = muestra.lote
        
        # Solo considerar muestras del muestreo inicial (no segundo muestreo)
        muestras_iniciales = lote.muestras.filter(es_segundo_muestreo=False)
        muestras_iniciales_pendientes = muestras_iniciales.filter(estado='PENDIENTE').count()
        
        response_data = {
            'mensaje': 'Resultado registrado exitosamente',
            'muestra': MuestraCafeSerializer(muestra).data,
            'lote_estado': lote.estado,
            'requiere_segundo_muestreo': False,
            'muestras_contaminadas': [],
            'separacion_requerida': False,
            'propietarios_a_separar': []
        }
        
        # Si todas las muestras iniciales han sido analizadas
        if muestras_iniciales_pendientes == 0:
            muestras_contaminadas = muestras_iniciales.filter(estado='CONTAMINADA')
            muestras_aprobadas = muestras_iniciales.filter(estado='APROBADA')
            
            if muestras_contaminadas.exists():
                # Hay contaminación, verificar si ya existe segundo muestreo
                tiene_segundo_muestreo = lote.muestras.filter(
                    es_segundo_muestreo=True,
                    muestra_original__in=muestras_contaminadas
                ).exists()
                
                if not tiene_segundo_muestreo:
                    # ✅ CREAR SEGUNDO MUESTREO AUTOMÁTICAMENTE
                    # Crear nuevas muestras para los propietarios con contaminación
                    nuevas_muestras = []
                    
                    # Obtener el número máximo de muestra existente para este lote
                    ultima_muestra = MuestraCafe.objects.filter(lote=lote).order_by('-id').first()
                    if ultima_muestra:
                        # Extraer el número de la última muestra (formato: LOTE-M##)
                        partes = ultima_muestra.numero_muestra.split('-M')
                        if len(partes) > 1:
                            ultimo_numero_str = partes[-1].replace('-S', '')  # Remover sufijo -S si existe
                            try:
                                contador_base = int(ultimo_numero_str) + 1
                            except (ValueError, IndexError):
                                contador_base = MuestraCafe.objects.filter(lote=lote).count() + 1
                        else:
                            contador_base = MuestraCafe.objects.filter(lote=lote).count() + 1
                    else:
                        contador_base = 1
                    
                    contador_actual = contador_base
                    
                    for muestra_contaminada in muestras_contaminadas:
                        # Generar número único de muestra para segundo muestreo
                        numero_muestra_segundo = f"{lote.numero_lote}-M{contador_actual:02d}-S"
                        
                        # Verificar que no exista ya una muestra con este número
                        while MuestraCafe.objects.filter(lote=lote, numero_muestra=numero_muestra_segundo).exists():
                            contador_actual += 1
                            numero_muestra_segundo = f"{lote.numero_lote}-M{contador_actual:02d}-S"
                        
                        nueva_muestra = MuestraCafe.objects.create(
                            lote=lote,
                            propietario=muestra_contaminada.propietario,
                            numero_muestra=numero_muestra_segundo,
                            analista=request.user,
                            es_segundo_muestreo=True,
                            muestra_original=muestra_contaminada
                        )
                        nuevas_muestras.append(nueva_muestra)
                        contador_actual += 1
                    
                    # Crear el proceso de seguimiento
                    proceso_seguimiento = ProcesoAnalisis.objects.create(
                        lote=lote,
                        tipo_proceso='SEGUIMIENTO',
                        usuario_proceso=request.user
                    )
                    
                    # Registrar creación automática del segundo muestreo en bitácora
                    RegistroBitacora.registrar_accion(
                        usuario=request.user,
                        accion='SEGUNDO_MUESTREO_AUTOMATICO',
                        modulo='PROCESOS',
                        descripcion=f'Segundo muestreo creado automáticamente para lote {lote.numero_lote} - {len(nuevas_muestras)} muestras de seguimiento creadas',
                        request=request,
                        lote=lote,
                        detalles_adicionales={
                            'propietarios_afectados': [m.propietario.nombre_completo for m in muestras_contaminadas],
                            'muestras_originales': [m.numero_muestra for m in muestras_contaminadas],
                            'nuevas_muestras': [m.numero_muestra for m in nuevas_muestras],
                            'proceso_seguimiento_id': proceso_seguimiento.id
                        }
                    )
                    
                    # Actualizar respuesta para indicar que se creó automáticamente
                    response_data['requiere_segundo_muestreo'] = False  # Ya se creó automáticamente
                    response_data['segundo_muestreo_creado'] = True
                    response_data['nuevas_muestras'] = MuestraCafeSerializer(nuevas_muestras, many=True).data
                    response_data['mensaje'] = f'Análisis completado. Se crearon automáticamente {len(nuevas_muestras)} muestras de segundo muestreo para confirmar contaminación.'
                    
                    # Mantener información de separación inteligente
                    response_data['separacion_requerida'] = True
                    propietarios_contaminados = []
                    quintales_contaminados = 0
                    for m_cont in muestras_contaminadas:
                        propietarios_contaminados.append({
                            'id': m_cont.propietario.id,
                            'nombre': m_cont.propietario.nombre_completo,
                            'quintales': m_cont.propietario.quintales_entregados,
                            'cedula': m_cont.propietario.cedula
                        })
                        quintales_contaminados += m_cont.propietario.quintales_entregados
                    
                    response_data['propietarios_a_separar'] = propietarios_contaminados
                    
                    # Actualizar observaciones del lote con separación inteligente
                    quintales_aprobados = sum([m.propietario.quintales_entregados for m in muestras_aprobadas])
                    total_quintales = lote.total_quintales
                    
                    lote.observaciones = f"""ANÁLISIS INICIAL COMPLETADO - SEGUNDO MUESTREO AUTOMÁTICO CREADO
                    
Resultado del primer análisis:
- Muestras analizadas: {muestras_iniciales.count()}
- Muestras aprobadas: {muestras_aprobadas.count()} 
- Muestras contaminadas: {muestras_contaminadas.count()}

SEGUNDO MUESTREO AUTOMÁTICO:
- Se crearon {len(nuevas_muestras)} muestras de seguimiento
- Propietarios en segundo muestreo: {', '.join([p['nombre'] for p in propietarios_contaminados])}

Separación potencial de quintales:
- Quintales APROBADOS (conservar): {quintales_aprobados} qq de {muestras_aprobadas.count()} propietarios
- Quintales EN SEGUNDO MUESTREO: {quintales_contaminados} qq de {muestras_contaminadas.count()} propietarios
- Total del lote: {total_quintales} qq

ESTADO ACTUAL: Esperando resultados del segundo muestreo para confirmar separación definitiva.

NOTA: El café de los propietarios con muestras aprobadas puede continuar en el proceso normal."""
                    
                    # Cambiar estado del lote a "SEPARACION_PENDIENTE"
                    lote.estado = 'SEPARACION_PENDIENTE'
                
                # Ya existe segundo muestreo, verificar si está completo
                muestras_segundo = lote.muestras.filter(es_segundo_muestreo=True)
                muestras_segundo_pendientes = muestras_segundo.filter(estado='PENDIENTE').count()
                
                if muestras_segundo_pendientes == 0:
                    # Segundo muestreo completado, aplicar separación inteligente
                    muestras_segundo_contaminadas = muestras_segundo.filter(estado='CONTAMINADA')
                    muestras_segundo_aprobadas = muestras_segundo.filter(estado='APROBADA')
                    
                    # Calcular quintales para separación final
                    quintales_originales = lote.total_quintales
                    propietarios_definitivamente_contaminados = []
                    propietarios_recuperados_segundo_muestreo = []
                    quintales_finales_contaminados = 0
                    quintales_finales_aprobados = 0
                    
                    # Propietarios que se confirmaron contaminados en segundo muestreo
                    for m_segundo_cont in muestras_segundo_contaminadas:
                        propietario = m_segundo_cont.propietario
                        propietarios_definitivamente_contaminados.append(propietario.nombre_completo)
                        quintales_finales_contaminados += propietario.quintales_entregados
                    
                    # Propietarios que se recuperaron en segundo muestreo
                    for m_segundo_aprob in muestras_segundo_aprobadas:
                        propietario = m_segundo_aprob.propietario
                        propietarios_recuperados_segundo_muestreo.append(propietario.nombre_completo)
                    
                    # Propietarios que estuvieron aprobados desde el inicio
                    for m_inicial_aprob in muestras_aprobadas:
                        quintales_finales_aprobados += m_inicial_aprob.propietario.quintales_entregados
                    
                    # Agregar quintales de propietarios recuperados en segundo muestreo
                    for m_segundo_aprob in muestras_segundo_aprobadas:
                        quintales_finales_aprobados += m_segundo_aprob.propietario.quintales_entregados
                    
                    if muestras_segundo_contaminadas.exists():
                        # ✅ ACTUALIZAR FÍSICAMENTE LOS QUINTALES DEL LOTE
                        lote.total_quintales = quintales_finales_aprobados
                        
                        # Ajustar peso proporcionalmente si existe
                        if lote.peso_total_inicial and quintales_originales > 0:
                            from decimal import Decimal
                            proporcion_limpia = Decimal(str(quintales_finales_aprobados)) / Decimal(str(quintales_originales))
                            lote.peso_total_inicial = lote.peso_total_inicial * proporcion_limpia
                        
                        if lote.peso_total_final and quintales_originales > 0:
                            from decimal import Decimal
                            proporcion_limpia = Decimal(str(quintales_finales_aprobados)) / Decimal(str(quintales_originales))
                            lote.peso_total_final = lote.peso_total_final * proporcion_limpia
                        
                        # Aplicar separación inteligente - Solo separar los confirmados contaminados
                        lote.estado = 'SEPARACION_APLICADA'
                        lote.observaciones = f"""SEPARACIÓN INTELIGENTE APLICADA - SEGUNDO MUESTREO COMPLETADO
                        
Resultado final del análisis:
- Total propietarios original: {lote.propietarios.count()}
- Muestras iniciales: {muestras_iniciales.count()}
- Segundo muestreo: {muestras_segundo.count()}

SEPARACIÓN REALIZADA:
✅ QUINTALES CONSERVADOS: {quintales_finales_aprobados} qq
   - Propietarios aprobados desde inicio: {', '.join([m.propietario.nombre_completo for m in muestras_aprobadas])}
   {"- Propietarios recuperados en 2do muestreo: " + ', '.join(propietarios_recuperados_segundo_muestreo) if propietarios_recuperados_segundo_muestreo else ""}

❌ QUINTALES SEPARADOS: {quintales_finales_contaminados} qq  
   - Propietarios con contaminación confirmada: {', '.join(propietarios_definitivamente_contaminados)}

RESUMEN:
- Quintales originales: {quintales_originales} qq
- El {round((quintales_finales_aprobados/quintales_originales)*100, 1)}% del lote ({quintales_finales_aprobados} qq) se conserva para continuar el proceso
- El {round((quintales_finales_contaminados/quintales_originales)*100, 1)}% del lote ({quintales_finales_contaminados} qq) se separa por contaminación confirmada

RESULTADO: SEPARACIÓN EXITOSA - El lote principal puede continuar el proceso de producción con {quintales_finales_aprobados} quintales."""
                        
                        response_data['mensaje'] = f'Segundo muestreo completado. Se separaron {quintales_finales_contaminados} quintales contaminados. {quintales_finales_aprobados} quintales continúan en el proceso.'
                        
                    else:
                        # Todos los del segundo muestreo salieron aprobados - recuperación total
                        lote.estado = 'APROBADO'
                        lote.observaciones = f"""LOTE COMPLETAMENTE RECUPERADO - SEGUNDO MUESTREO EXITOSO
                        
Resultado excepcional:
- Muestras iniciales contaminadas: {muestras_contaminadas.count()}
- Todas las muestras de segundo muestreo: APROBADAS ✅

RECUPERACIÓN TOTAL:
- El 100% del lote ({lote.total_quintales} quintales) ha sido aprobado
- No se requiere separación de quintales
- Todos los propietarios pueden continuar en el proceso

Este resultado indica que la contaminación inicial fue un falso positivo o se corrigió satisfactoriamente.

RESULTADO: LOTE COMPLETAMENTE APROBADO - Café en óptimas condiciones para continuar producción."""
                        
                        response_data['mensaje'] = '¡Excelente! Segundo muestreo exitoso. Toda la contaminación inicial se ha resuelto. El lote completo puede continuar.'
                    
                    # Finalizar todos los procesos abiertos
                    procesos_abiertos = lote.procesos.filter(fecha_finalizacion__isnull=True)
                    for proceso in procesos_abiertos:
                        proceso.fecha_finalizacion = timezone.now()
                        proceso.aprobado = (lote.estado in ['APROBADO', 'SEPARACION_APLICADA'])
                        proceso.resultado_general = lote.observaciones
                        proceso.save()
                
        lote.save()
        response_data['lote_estado'] = lote.estado
        
        return Response(response_data)
        
    except MuestraCafe.DoesNotExist:
        return Response({'error': 'Muestra no encontrada'}, status=status.HTTP_404_NOT_FOUND)

# Vistas para listar muestras
class MuestraCafeListView(generics.ListAPIView):
    serializer_class = MuestraCafeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = MuestraCafe.objects.all().order_by('-fecha_toma_muestra')
        lote_id = self.request.query_params.get('lote_id')
        estado = self.request.query_params.get('estado')
        
        if lote_id:
            queryset = queryset.filter(lote_id=lote_id)
        if estado:
            queryset = queryset.filter(estado=estado)
            
        return queryset

# Vista para obtener estadísticas
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def estadisticas_procesos(request):
    total_lotes = LoteCafe.objects.count()
    lotes_pendientes = LoteCafe.objects.filter(estado='PENDIENTE').count()
    lotes_en_proceso = LoteCafe.objects.filter(estado='EN_PROCESO').count()
    lotes_aprobados = LoteCafe.objects.filter(estado='APROBADO').count()
    lotes_rechazados = LoteCafe.objects.filter(estado='RECHAZADO').count()
    
    total_muestras = MuestraCafe.objects.count()
    muestras_pendientes = MuestraCafe.objects.filter(estado='PENDIENTE').count()
    muestras_aprobadas = MuestraCafe.objects.filter(estado='APROBADA').count()
    muestras_contaminadas = MuestraCafe.objects.filter(estado='CONTAMINADA').count()
    
    return Response({
        'lotes': {
            'total': total_lotes,
            'pendientes': lotes_pendientes,
            'en_proceso': lotes_en_proceso,
            'aprobados': lotes_aprobados,
            'rechazados': lotes_rechazados
        },
        'muestras': {
            'total': total_muestras,
            'pendientes': muestras_pendientes,
            'aprobadas': muestras_aprobadas,
            'contaminadas': muestras_contaminadas
        }
    })

# Vista para crear segundo muestreo cuando hay contaminación
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def crear_segundo_muestreo(request):
    """
    Crear segundo muestreo para propietarios con muestras contaminadas
    """
    lote_id = request.data.get('lote_id')
    muestras_contaminadas_ids = request.data.get('muestras_contaminadas', [])
    
    try:
        lote = LoteCafe.objects.get(id=lote_id)
        
        # Verificar que el lote tenga muestras contaminadas
        muestras_contaminadas = MuestraCafe.objects.filter(
            id__in=muestras_contaminadas_ids,
            lote=lote,
            estado='CONTAMINADA',
            es_segundo_muestreo=False
        )
        
        if not muestras_contaminadas:
            return Response({'error': 'No se encontraron muestras contaminadas válidas para segundo muestreo'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Crear el proceso de seguimiento
        proceso_seguimiento = ProcesoAnalisis.objects.create(
            lote=lote,
            tipo_proceso='SEGUIMIENTO',
            usuario_proceso=request.user
        )
        
        # Registrar inicio del segundo muestreo en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='SEGUNDO_MUESTREO',
            modulo='PROCESOS',
            descripcion=f'Segundo muestreo iniciado para lote {lote.numero_lote} - {len(muestras_contaminadas)} propietarios con contaminación',
            request=request,
            lote=lote,
            detalles_adicionales={
                'propietarios_afectados': [m.propietario.nombre_completo for m in muestras_contaminadas],
                'muestras_originales': [m.numero_muestra for m in muestras_contaminadas]
            }
        )
        
        # Obtener el número máximo de muestra existente para este lote
        ultima_muestra = MuestraCafe.objects.filter(lote=lote).order_by('-id').first()
        if ultima_muestra:
            # Extraer el número de la última muestra (formato: LOTE-M##)
            ultimo_numero = ultima_muestra.numero_muestra.split('-M')[-1]
            try:
                contador_base = int(ultimo_numero) + 1
            except (ValueError, IndexError):
                contador_base = MuestraCafe.objects.filter(lote=lote).count() + 1
        else:
            contador_base = 1
        
        # Crear nuevas muestras para los propietarios con contaminación
        nuevas_muestras = []
        contador_actual = contador_base
        
        for muestra_contaminada in muestras_contaminadas:
            # Generar número único de muestra para segundo muestreo
            numero_muestra_segundo = f"{lote.numero_lote}-M{contador_actual:02d}-S"
            
            # Verificar que no exista ya una muestra con este número
            while MuestraCafe.objects.filter(lote=lote, numero_muestra=numero_muestra_segundo).exists():
                contador_actual += 1
                numero_muestra_segundo = f"{lote.numero_lote}-M{contador_actual:02d}-S"
            
            nueva_muestra = MuestraCafe.objects.create(
                lote=lote,
                propietario=muestra_contaminada.propietario,
                numero_muestra=numero_muestra_segundo,
                analista=request.user,
                es_segundo_muestreo=True,
                muestra_original=muestra_contaminada
            )
            nuevas_muestras.append(nueva_muestra)
            contador_actual += 1
        
        return Response({
            'mensaje': f'Se crearon {len(nuevas_muestras)} muestras de segundo muestreo exitosamente',
            'proceso_id': proceso_seguimiento.id,
            'nuevas_muestras': MuestraCafeSerializer(nuevas_muestras, many=True).data
        }, status=status.HTTP_201_CREATED)
        
    except LoteCafe.DoesNotExist:
        return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vista para generar reporte de separación de quintales
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def generar_reporte_separacion(request, lote_id):
    """
    Generar reporte detallado para separación de quintales contaminados
    """
    try:
        lote = LoteCafe.objects.get(id=lote_id)
        
        # Obtener todas las muestras del lote (iniciales y de seguimiento)
        muestras_iniciales = lote.muestras.filter(es_segundo_muestreo=False)
        muestras_seguimiento = lote.muestras.filter(es_segundo_muestreo=True)
        
        # Analizar propietarios y sus estados
        propietarios_aprobados = []
        propietarios_contaminados = []
        propietarios_sin_analizar = []
        
        for propietario in lote.propietarios.all():
            # Buscar muestra inicial del propietario
            muestra_inicial = muestras_iniciales.filter(propietario=propietario).first()
            
            if not muestra_inicial or muestra_inicial.estado == 'PENDIENTE':
                # Sin analizar
                propietarios_sin_analizar.append({
                    'propietario': PropietarioCafeSerializer(propietario).data,
                    'estado_muestra': 'PENDIENTE',
                    'accion': 'PENDIENTE_ANALISIS'
                })
                continue
            
            if muestra_inicial.estado == 'APROBADA':
                # Aprobado en primera instancia
                propietarios_aprobados.append({
                    'propietario': PropietarioCafeSerializer(propietario).data,
                    'estado_muestra': 'APROBADA',
                    'accion': 'CONSERVAR',
                    'observaciones': 'Aprobado en análisis inicial'
                })
            elif muestra_inicial.estado == 'CONTAMINADA':
                # Contaminado en primera instancia, verificar segundo muestreo
                muestra_seguimiento = muestras_seguimiento.filter(propietario=propietario).first()
                
                if muestra_seguimiento:
                    if muestra_seguimiento.estado == 'APROBADA':
                        # Recuperado en segundo muestreo
                        propietarios_aprobados.append({
                            'propietario': PropietarioCafeSerializer(propietario).data,
                            'estado_muestra': 'APROBADA_SEGUNDO',
                            'accion': 'CONSERVAR',
                            'observaciones': 'Contaminación inicial, pero aprobado en segundo muestreo'
                        })
                    elif muestra_seguimiento.estado == 'CONTAMINADA':
                        # Confirmado contaminado
                        propietarios_contaminados.append({
                            'propietario': PropietarioCafeSerializer(propietario).data,
                            'estado_muestra': 'CONTAMINADA_CONFIRMADA',
                            'accion': 'SEPARAR',
                            'observaciones': 'Contaminación confirmada en segundo muestreo'
                        })
                    else:
                        # Segundo muestreo pendiente
                        propietarios_sin_analizar.append({
                            'propietario': PropietarioCafeSerializer(propietario).data,
                            'estado_muestra': 'SEGUNDO_PENDIENTE',
                            'accion': 'PENDIENTE_SEGUNDO_ANALISIS'
                        })
                else:
                    # Contaminado pero sin segundo muestreo
                    propietarios_contaminados.append({
                        'propietario': PropietarioCafeSerializer(propietario).data,
                        'estado_muestra': 'CONTAMINADA',
                        'accion': 'SEPARAR',
                        'observaciones': 'Contaminación detectada (requiere confirmación)'
                    })
        
        # Calcular totales
        total_quintales_aprobados = sum([p['propietario']['quintales_entregados'] for p in propietarios_aprobados])
        total_quintales_contaminados = sum([p['propietario']['quintales_entregados'] for p in propietarios_contaminados])
        total_quintales_pendientes = sum([p['propietario']['quintales_entregados'] for p in propietarios_sin_analizar])
        
        # Determinar recomendación del lote
        if len(propietarios_contaminados) == 0 and len(propietarios_sin_analizar) == 0:
            recomendacion_lote = "APROBAR_COMPLETO"
            mensaje_recomendacion = "Todo el lote puede ser aprobado"
        elif len(propietarios_contaminados) > 0 and len(propietarios_aprobados) > 0:
            recomendacion_lote = "SEPARACION_PARCIAL"
            mensaje_recomendacion = "Separar quintales contaminados, conservar el resto"
        elif len(propietarios_contaminados) == len(lote.propietarios.all()):
            recomendacion_lote = "RECHAZAR_COMPLETO"
            mensaje_recomendacion = "Todo el lote debe ser rechazado"
        else:
            recomendacion_lote = "ANALISIS_PENDIENTE"
            mensaje_recomendacion = "Completar análisis antes de tomar decisión final"
        
        return Response({
            'lote': LoteCafeSerializer(lote).data,
            'propietarios_aprobados': propietarios_aprobados,
            'propietarios_contaminados': propietarios_contaminados,
            'propietarios_sin_analizar': propietarios_sin_analizar,
            'totales': {
                'quintales_aprobados': total_quintales_aprobados,
                'quintales_contaminados': total_quintales_contaminados,
                'quintales_pendientes': total_quintales_pendientes,
                'total_lote': lote.total_quintales
            },
            'recomendacion': {
                'tipo': recomendacion_lote,
                'mensaje': mensaje_recomendacion
            },
            'fecha_reporte': timezone.now().isoformat()
        })
        
    except LoteCafe.DoesNotExist:
        return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)

# Vista para actualizar lote existente
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def actualizar_lote(request, lote_id):
    """
    Actualizar un lote existente con propietarios
    """
    try:
        lote = LoteCafe.objects.get(id=lote_id)
        
        # Actualizar campos del lote
        lote.numero_lote = request.data.get('numero_lote', lote.numero_lote)
        lote.organizacion_id = request.data.get('organizacion', lote.organizacion_id)
        lote.fecha_entrega = request.data.get('fecha_entrega', lote.fecha_entrega)
        lote.total_quintales = request.data.get('total_quintales', lote.total_quintales)
        lote.observaciones = request.data.get('observaciones', lote.observaciones)
        
        # Actualizar propietarios si se proporcionan
        propietarios_data = request.data.get('propietarios', [])
        if propietarios_data:
            # Eliminar propietarios existentes
            PropietarioCafe.objects.filter(lote=lote).delete()
            
            # Crear nuevos propietarios
            for prop_data in propietarios_data:
                PropietarioCafe.objects.create(
                    lote=lote,
                    nombre_completo=prop_data.get('nombre_completo'),
                    cedula=prop_data.get('cedula'),
                    quintales_entregados=prop_data.get('quintales_entregados'),
                    telefono=prop_data.get('telefono', ''),
                    direccion=prop_data.get('direccion', '')
                )
        
        lote.save()
        
        return Response({
            'mensaje': 'Lote actualizado exitosamente',
            'lote': LoteCafeSerializer(lote).data
        })
        
    except LoteCafe.DoesNotExist:
        return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RegistroBitacoraViewSet(viewsets.ModelViewSet):
    serializer_class = RegistroBitacoraSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['descripcion', 'usuario__username', 'lote__numero_lote', 'muestra__numero_muestra']
    ordering_fields = ['fecha', 'accion', 'modulo', 'usuario__username']
    ordering = ['-fecha']
    filterset_fields = ['accion', 'modulo', 'usuario', 'fecha']
    
    def get_queryset(self):
        queryset = RegistroBitacora.objects.all()
        
        # Filtros adicionales por parámetros de query
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if fecha_desde:
            queryset = queryset.filter(fecha__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha__date__lte=fecha_hasta)
            
        return queryset
    
    def create(self, request, *args, **kwargs):
        # Registrar la acción de crear un registro manual
        try:
            response = super().create(request, *args, **kwargs)
            
            # Registrar esta acción en la bitácora
            RegistroBitacora.registrar_accion(
                usuario=request.user,
                accion='CREAR_REGISTRO_MANUAL',
                modulo='SISTEMA',
                descripcion=f'Registro manual creado: {request.data.get("descripcion", "")}',
                request=request
            )
            
            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def estadisticas_bitacora(request):
    """
    Obtener estadísticas generales de la bitácora
    """
    try:
        # Estadísticas generales
        total_registros = RegistroBitacora.objects.count()
        registros_hoy = RegistroBitacora.objects.filter(fecha__date=timezone.now().date()).count()
        usuarios_activos = RegistroBitacora.objects.values('usuario').distinct().count()
        
        # Estadísticas por acción
        acciones_stats = RegistroBitacora.objects.values('accion').annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Estadísticas por módulo
        modulos_stats = RegistroBitacora.objects.values('modulo').annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Actividad por día (últimos 7 días)
        fecha_inicio = timezone.now().date() - timedelta(days=6)
        actividad_diaria = []
        
        for i in range(7):
            fecha = fecha_inicio + timedelta(days=i)
            registros_dia = RegistroBitacora.objects.filter(fecha__date=fecha).count()
            actividad_diaria.append({
                'fecha': fecha.strftime('%Y-%m-%d'),
                'registros': registros_dia
            })
        
        # Usuarios más activos
        usuarios_activos_stats = RegistroBitacora.objects.values(
            'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            total_acciones=Count('id')
        ).order_by('-total_acciones')[:10]
        
        return Response({
            'total_registros': total_registros,
            'registros_hoy': registros_hoy,
            'usuarios_activos': usuarios_activos,
            'acciones_stats': acciones_stats,
            'modulos_stats': modulos_stats,
            'actividad_diaria': actividad_diaria,
            'usuarios_activos_stats': usuarios_activos_stats
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def exportar_bitacora_csv(request):
    """
    Exportar registros de bitácora a CSV
    """
    try:
        # Obtener filtros del request
        filtros = request.data.get('filtros', {})
        
        queryset = RegistroBitacora.objects.all()
        
        # Aplicar filtros
        if filtros.get('fecha_desde'):
            queryset = queryset.filter(fecha__date__gte=filtros['fecha_desde'])
        if filtros.get('fecha_hasta'):
            queryset = queryset.filter(fecha__date__lte=filtros['fecha_hasta'])
        if filtros.get('accion'):
            queryset = queryset.filter(accion=filtros['accion'])
        if filtros.get('modulo'):
            queryset = queryset.filter(modulo=filtros['modulo'])
        if filtros.get('usuario'):
            queryset = queryset.filter(usuario_id=filtros['usuario'])
        
        # Registrar la acción de exportación
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='EXPORTAR_CSV',
            modulo='REPORTES',
            descripcion=f'Exportación CSV de bitácora con {queryset.count()} registros',
            request=request,
            detalles_adicionales={'filtros_aplicados': filtros}
        )
        
        # Crear respuesta con los datos para el frontend
        datos_export = []
        for registro in queryset.order_by('-fecha'):
            datos_export.append({
                'fecha': registro.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                'usuario': registro.usuario.username,
                'accion': registro.get_accion_display(),
                'modulo': registro.get_modulo_display(),
                'descripcion': registro.descripcion,
                'lote': registro.lote.numero_lote if registro.lote else '',
                'muestra': registro.muestra.numero_muestra if registro.muestra else '',
                'ip_address': registro.ip_address or ''
            })
        
        return Response({
            'success': True,
            'total_registros': len(datos_export),
            'datos': datos_export
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # Si el login fue exitoso, registrar en bitácora y verificar perfil
        if response.status_code == 200:
            from rest_framework_simplejwt.tokens import UntypedToken
            from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
            from django.contrib.auth import get_user_model
            
            try:
                # Obtener datos del usuario
                username = request.data.get('username')
                if username:
                    User = get_user_model()
                    user = User.objects.get(username=username)
                    
                    # Asegurar que el usuario tiene un perfil
                    if not hasattr(user, 'profile'):
                        from .models import UserProfile
                        UserProfile.objects.create(user=user)
                        user.refresh_from_db()
                    
                    # Agregar información del usuario a la respuesta
                    user_data = {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'nombre_completo': user.get_full_name() or user.username,
                        'rol': user.profile.rol,
                        'rol_display': user.profile.get_rol_display(),
                        'activo': user.profile.activo
                    }
                    
                    # Agregar la información del usuario a la respuesta
                    response.data['user'] = user_data
                    
                    # Registrar login exitoso
                    RegistroBitacora.registrar_accion(
                        usuario=user,
                        accion='LOGIN',
                        modulo='AUTENTICACION',
                        descripcion=f'Inicio de sesión exitoso para {user.username} (Rol: {user.profile.rol})',
                        request=request,
                        detalles_adicionales={'rol': user.profile.rol}
                    )
            except Exception as e:
                # Si hay algún error, agregar información de debug
                response.data['debug_error'] = str(e)
        
        return response

# Vista para listar y crear insumos
class InsumoListCreateView(generics.ListCreateAPIView):
    queryset = Insumo.objects.filter(activo=True)
    serializer_class = InsumoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['nombre', 'codigo', 'tipo', 'marca', 'modelo', 'descripcion']
    ordering_fields = ['nombre', 'tipo', 'cantidad_disponible', 'fecha_creacion']
    ordering = ['nombre']
    filterset_fields = ['tipo', 'activo', 'unidad_medida']
    
    def perform_create(self, serializer):
        insumo = serializer.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='CREAR_INSUMO',
            modulo='INVENTARIO',
            descripcion=f'Insumo creado: {insumo.nombre} ({insumo.codigo}) - Tipo: {insumo.get_tipo_display()} - Cantidad: {insumo.cantidad_disponible} {insumo.get_unidad_medida_display()}',
            request=self.request,
            detalles_adicionales={
                'insumo_id': insumo.id,
                'nombre': insumo.nombre,
                'codigo': insumo.codigo,
                'tipo': insumo.tipo,
                'cantidad_inicial': float(insumo.cantidad_disponible),
                'unidad_medida': insumo.unidad_medida
            }
        )

# Vista para ver detalles de insumo
class InsumoDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_update(self, serializer):
        insumo_anterior = self.get_object()
        cantidad_anterior = insumo_anterior.cantidad_disponible
        
        insumo = serializer.save()
        
        # Registrar cambios en bitácora
        cambios = []
        if cantidad_anterior != insumo.cantidad_disponible:
            cambios.append(f'Cantidad: {cantidad_anterior} → {insumo.cantidad_disponible}')
        
        if cambios:
            RegistroBitacora.registrar_accion(
                usuario=self.request.user,
                accion='ACTUALIZAR_INSUMO',
                modulo='INVENTARIO',
                descripcion=f'Insumo actualizado: {insumo.nombre} - {", ".join(cambios)}',
                request=self.request,
                detalles_adicionales={
                    'insumo_id': insumo.id,
                    'cambios': cambios,
                    'cantidad_anterior': float(cantidad_anterior),
                    'cantidad_nueva': float(insumo.cantidad_disponible)
                }
            )

# Nuevo endpoint para obtener opciones de tipos de insumos
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def obtener_tipos_insumos(request):
    """
    Endpoint para obtener las opciones de tipos de insumos disponibles
    """
    tipos_insumos = [
        {'id': 'MAQUINARIA', 'nombre': 'Maquinaria', 'tipo_display': 'Maquinaria'},
        {'id': 'BALANZA', 'nombre': 'Balanza/Báscula', 'tipo_display': 'Balanza/Báscula'},
        {'id': 'CONTENEDOR', 'nombre': 'Contenedor/Saco/Bolsa', 'tipo_display': 'Contenedor/Saco/Bolsa'},
        {'id': 'HERRAMIENTA', 'nombre': 'Herramienta', 'tipo_display': 'Herramienta'},
        {'id': 'EQUIPO_MEDICION', 'nombre': 'Equipo de Medición', 'tipo_display': 'Equipo de Medición'},
        {'id': 'MATERIAL_EMPAQUE', 'nombre': 'Material de Empaque', 'tipo_display': 'Material de Empaque'},
        {'id': 'EQUIPO_TRANSPORTE', 'nombre': 'Equipo de Transporte', 'tipo_display': 'Equipo de Transporte'},
        {'id': 'OTRO', 'nombre': 'Otro', 'tipo_display': 'Otro'},
    ]
    
    unidades_medida = [
        {'id': 'UNIDAD', 'nombre': 'Unidad'},
        {'id': 'KG', 'nombre': 'Kilogramos'},
        {'id': 'LIBRA', 'nombre': 'Libras'},
        {'id': 'METRO', 'nombre': 'Metros'},
        {'id': 'LITRO', 'nombre': 'Litros'},
        {'id': 'SACO', 'nombre': 'Sacos'},
        {'id': 'CAJA', 'nombre': 'Cajas'},
        {'id': 'PAR', 'nombre': 'Par'},
    ]
    
    return Response({
        'success': True,
        'tipos_disponibles': tipos_insumos,
        'unidades_medida': unidades_medida,
        'total_tipos': len(tipos_insumos),
        'total_unidades': len(unidades_medida)
    })

# Vista para obtener estadísticas de inventario
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def estadisticas_inventario(request):
    """
    Obtener estadísticas del inventario de insumos
    """
    try:
        # Estadísticas generales
        total_insumos = Insumo.objects.filter(activo=True).count()
        insumos_agotados = Insumo.objects.filter(activo=True, cantidad_disponible=0).count()
        insumos_bajo_stock = Insumo.objects.filter(
            activo=True,
            cantidad_disponible__gt=0,
            cantidad_disponible__lte=models.F('cantidad_minima')
        ).count()
        
        # Estadísticas por tipo
        tipos_stats = Insumo.objects.filter(activo=True).values('tipo').annotate(
            total=Count('id'),
            agotados=Count('id', filter=models.Q(cantidad_disponible=0)),
            bajo_stock=Count('id', filter=models.Q(
                cantidad_disponible__gt=0,
                cantidad_disponible__lte=models.F('cantidad_minima')
            ))
        ).order_by('-total')
        
        # Agregar nombres legibles a los tipos
        for stat in tipos_stats:
            tipo_choice = next((choice for choice in Insumo.TIPOS_INSUMO if choice[0] == stat['tipo']), None)
            stat['tipo_display'] = tipo_choice[1] if tipo_choice else stat['tipo']
        
        # Insumos que necesitan reposición urgente
        insumos_criticos = Insumo.objects.filter(
            activo=True,
            cantidad_disponible=0
        ).values('id', 'nombre', 'codigo', 'tipo', 'cantidad_minima')[:10]
        
        # Insumos con bajo stock
        insumos_bajo_stock_detalle = Insumo.objects.filter(
            activo=True,
            cantidad_disponible__gt=0,
            cantidad_disponible__lte=models.F('cantidad_minima')
        ).values('id', 'nombre', 'codigo', 'tipo', 'cantidad_disponible', 'cantidad_minima')[:10]
        
        return Response({
            'estadisticas_generales': {
                'total_insumos': total_insumos,
                'insumos_agotados': insumos_agotados,
                'insumos_bajo_stock': insumos_bajo_stock,
                'insumos_normal': total_insumos - insumos_agotados - insumos_bajo_stock,
                'porcentaje_agotados': round((insumos_agotados / total_insumos * 100), 2) if total_insumos > 0 else 0,
                'porcentaje_bajo_stock': round((insumos_bajo_stock / total_insumos * 100), 2) if total_insumos > 0 else 0
            },
            'tipos_stats': tipos_stats,
            'insumos_criticos': insumos_criticos,
            'insumos_bajo_stock': insumos_bajo_stock_detalle
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vista para actualizar stock de insumo
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def actualizar_stock_insumo(request, insumo_id):
    """
    Actualizar el stock de un insumo específico
    """
    try:
        from decimal import Decimal
        
        insumo = Insumo.objects.get(id=insumo_id, activo=True)
        
        nueva_cantidad = request.data.get('nueva_cantidad')
        tipo_movimiento = request.data.get('tipo_movimiento', 'AJUSTE')  # ENTRADA, SALIDA, AJUSTE
        observaciones = request.data.get('observaciones', '')
        
        if nueva_cantidad is None:
            return Response({'error': 'La nueva cantidad es requerida'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            nueva_cantidad = Decimal(str(nueva_cantidad))
            if nueva_cantidad < 0:
                return Response({'error': 'La cantidad no puede ser negativa'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': 'La cantidad debe ser un número válido'}, status=status.HTTP_400_BAD_REQUEST)
        
        cantidad_anterior = Decimal(str(insumo.cantidad_disponible))
        diferencia = nueva_cantidad - cantidad_anterior
        
        # Actualizar la cantidad
        insumo.cantidad_disponible = nueva_cantidad
        insumo.save()
        
        # Determinar el tipo de acción para la bitácora
        if diferencia > 0:
            accion_descripcion = f'ENTRADA de inventario: +{diferencia} {insumo.get_unidad_medida_display()}'
        elif diferencia < 0:
            accion_descripcion = f'SALIDA de inventario: {diferencia} {insumo.get_unidad_medida_display()}'
        else:
            accion_descripcion = 'AJUSTE de inventario: sin cambio en cantidad'
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='ACTUALIZAR_STOCK',
            modulo='INVENTARIO',
            descripcion=f'{accion_descripcion} - {insumo.nombre} - Cantidad anterior: {cantidad_anterior} → Nueva: {nueva_cantidad}',
            request=request,
            detalles_adicionales={
                'insumo_id': insumo.id,
                'insumo_nombre': insumo.nombre,
                'cantidad_anterior': float(cantidad_anterior),
                'cantidad_nueva': float(nueva_cantidad),
                'diferencia': float(diferencia),
                'tipo_movimiento': tipo_movimiento,
                'observaciones': observaciones
            }
        )
        
        return Response({
            'mensaje': 'Stock actualizado exitosamente',
            'insumo': InsumoSerializer(insumo).data,
            'movimiento': {
                'cantidad_anterior': float(cantidad_anterior),
                'cantidad_nueva': float(nueva_cantidad),
                'diferencia': float(diferencia),
                'tipo_movimiento': tipo_movimiento
            }
        })
        
    except Insumo.DoesNotExist:
        return Response({'error': 'Insumo no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vistas para registros de descarga
class RegistroDescargaListCreateView(generics.ListCreateAPIView):
    queryset = RegistroDescarga.objects.all().order_by('-fecha_registro')
    serializer_class = RegistroDescargaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['empleado__username', 'empleado__first_name', 'empleado__last_name', 'lote__numero_lote']
    ordering_fields = ['fecha_registro', 'peso_descargado', 'tiempo_descarga_minutos']
    ordering = ['-fecha_registro']
    filterset_fields = ['empleado', 'lote', 'fecha_registro']
    
    def perform_create(self, serializer):
        descarga = serializer.save()
        
        # Manejar descuento de stock automático para ciertos tipos de insumos
        if descarga.insumo and descarga.cantidad_insumo_usado:
            tipos_que_restan = ['CONTENEDOR', 'EQUIPO_MEDICION', 'OTRO']
            if descarga.insumo.tipo in tipos_que_restan:
                # Restar del stock
                insumo = descarga.insumo
                cantidad_anterior = insumo.cantidad_disponible
                insumo.cantidad_disponible -= descarga.cantidad_insumo_usado
                insumo.save()
                
                # Registrar el movimiento de stock en bitácora adicional
                RegistroBitacora.registrar_accion(
                    usuario=self.request.user,
                    accion='ACTUALIZAR_STOCK',
                    modulo='INVENTARIO',
                    descripcion=f'Stock reducido automáticamente por uso en descarga - {insumo.nombre} - Cantidad anterior: {cantidad_anterior} → Nueva: {insumo.cantidad_disponible}',
                    request=self.request,
                    detalles_adicionales={
                        'insumo_id': insumo.id,
                        'insumo_nombre': insumo.nombre,
                        'cantidad_anterior': float(cantidad_anterior),
                        'cantidad_nueva': float(insumo.cantidad_disponible),
                        'cantidad_usada': float(descarga.cantidad_insumo_usado),
                        'descarga_id': descarga.id,
                        'tipo_movimiento': 'DESCUENTO_AUTOMATICO',
                        'razon': 'Uso en descarga de lote'
                    }
                )
        
        # Registrar en bitácora la descarga
        insumo_info = ""
        if descarga.insumo:
            if descarga.cantidad_insumo_usado:
                insumo_info = f" - Insumo: {descarga.insumo.nombre} ({descarga.insumo.codigo}) - Cantidad usada: {descarga.cantidad_insumo_usado} {descarga.insumo.get_unidad_medida_display()}"
            else:
                insumo_info = f" - Insumo: {descarga.insumo.nombre} ({descarga.insumo.codigo})"
        
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='REGISTRAR_DESCARGA',
            modulo='PERSONAL',
            descripcion=f'Descarga registrada: {descarga.peso_descargado} kg - Lote {descarga.lote.numero_lote} - Tiempo: {descarga.tiempo_descarga_minutos or "N/A"} min{insumo_info}',
            request=self.request,
            lote=descarga.lote,
            detalles_adicionales={
                'descarga_id': descarga.id,
                'peso_descargado': float(descarga.peso_descargado),
                'tiempo_descarga_minutos': descarga.tiempo_descarga_minutos,
                'empleado': descarga.empleado.get_full_name() or descarga.empleado.username,
                'insumo_id': descarga.insumo.id if descarga.insumo else None,
                'insumo_nombre': descarga.insumo.nombre if descarga.insumo else None,
                'insumo_tipo': descarga.insumo.get_tipo_display() if descarga.insumo else None,
                'cantidad_insumo_usado': float(descarga.cantidad_insumo_usado) if descarga.cantidad_insumo_usado else None
            }
        )

class RegistroDescargaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = RegistroDescarga.objects.all()
    serializer_class = RegistroDescargaSerializer
    permission_classes = [permissions.IsAuthenticated]

# Vistas para uso de maquinaria/insumos
class RegistroUsoMaquinariaListCreateView(generics.ListCreateAPIView):
    queryset = RegistroUsoMaquinaria.objects.all().order_by('-fecha_registro')
    serializer_class = RegistroUsoMaquinariaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['empleado__username', 'maquinaria__nombre', 'lote__numero_lote']
    ordering_fields = ['fecha_registro', 'tiempo_uso_minutos', 'peso_total_descargado']
    ordering = ['-fecha_registro']
    filterset_fields = ['empleado', 'maquinaria', 'tipo_maquinaria', 'lote']
    
    def perform_create(self, serializer):
        uso_maquinaria = serializer.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='REGISTRAR_USO_MAQUINARIA',
            modulo='MAQUINARIA',
            descripcion=f'Uso de maquinaria registrado: {uso_maquinaria.get_tipo_maquinaria_display()} - Lote {uso_maquinaria.lote.numero_lote} - Tiempo: {uso_maquinaria.tiempo_uso_minutos} min - Peso: {uso_maquinaria.peso_total_descargado} kg',
            request=self.request,
            lote=uso_maquinaria.lote,
            detalles_adicionales={
                'uso_maquinaria_id': uso_maquinaria.id,
                'tipo_maquinaria': uso_maquinaria.tipo_maquinaria,
                'maquinaria_nombre': uso_maquinaria.maquinaria.nombre if uso_maquinaria.maquinaria else None,
                'tiempo_uso_minutos': uso_maquinaria.tiempo_uso_minutos,
                'peso_total_descargado': float(uso_maquinaria.peso_total_descargado),
                'empleado': uso_maquinaria.empleado.get_full_name() or uso_maquinaria.empleado.username
            }
        )

class RegistroUsoMaquinariaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = RegistroUsoMaquinaria.objects.all()
    serializer_class = RegistroUsoMaquinariaSerializer
    permission_classes = [permissions.IsAuthenticated]

# Vistas para propietarios maestros
class PropietarioMaestroListCreateView(generics.ListCreateAPIView):
    queryset = PropietarioMaestro.objects.filter(activo=True).order_by('nombre_completo')
    serializer_class = PropietarioMaestroSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre_completo', 'cedula', 'telefono']
    ordering_fields = ['nombre_completo', 'fecha_registro']
    ordering = ['nombre_completo']

class PropietarioMaestroDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PropietarioMaestro.objects.all()
    serializer_class = PropietarioMaestroSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_update(self, serializer):
        propietario_anterior = self.get_object()
        propietario = serializer.save()
        
        # Registrar cambios en bitácora
        cambios = []
        if propietario_anterior.nombre_completo != propietario.nombre_completo:
            cambios.append(f'Nombre: {propietario_anterior.nombre_completo} → {propietario.nombre_completo}')
        if propietario_anterior.telefono != propietario.telefono:
            cambios.append(f'Teléfono: {propietario_anterior.telefono} → {propietario.telefono}')
        if propietario_anterior.departamento != propietario.departamento:
            cambios.append(f'Departamento: {propietario_anterior.departamento} → {propietario.departamento}')
        if propietario_anterior.municipio != propietario.municipio:
            cambios.append(f'Municipio: {propietario_anterior.municipio} → {propietario.municipio}')
        
        if cambios:
            RegistroBitacora.registrar_accion(
                usuario=self.request.user,
                accion='ACTUALIZAR_PROPIETARIO',
                modulo='PERSONAL',
                descripcion=f'Propietario maestro actualizado: {propietario.nombre_completo} ({propietario.cedula}) - {", ".join(cambios)}',
                request=self.request,
                detalles_adicionales={
                    'propietario_id': propietario.id,
                    'cedula': propietario.cedula,
                    'cambios': cambios
                }
            )

    def perform_destroy(self, instance):
        # En lugar de eliminar, marcar como inactivo
        instance.activo = False
        instance.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='ELIMINAR_PROPIETARIO',
            modulo='PERSONAL',
            descripcion=f'Propietario maestro desactivado: {instance.nombre_completo} ({instance.cedula}) - Total entregas históricas: {instance.total_entregas}',
            request=self.request,
            detalles_adicionales={
                'propietario_id': instance.id,
                'cedula': instance.cedula,
                'total_entregas': instance.total_entregas,
                'total_quintales_historicos': float(instance.total_quintales_historicos)
            }
        )

# Vista adicional para reactivar propietarios
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reactivar_propietario_maestro(request, propietario_id):
    """
    Reactivar un propietario maestro que fue desactivado
    """
    try:
        propietario = PropietarioMaestro.objects.get(id=propietario_id, activo=False)
        propietario.activo = True
        propietario.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='REACTIVAR_PROPIETARIO',
            modulo='PERSONAL',
            descripcion=f'Propietario maestro reactivado: {propietario.nombre_completo} ({propietario.cedula})',
            request=request,
            detalles_adicionales={
                'propietario_id': propietario.id,
                'cedula': propietario.cedula
            }
        )
        
        return Response({
            'mensaje': 'Propietario reactivado exitosamente',
            'propietario': PropietarioMaestroSerializer(propietario).data
        })
        
    except PropietarioMaestro.DoesNotExist:
        return Response({'error': 'Propietario no encontrado o ya está activo'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vista para obtener propietarios inactivos
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def propietarios_inactivos(request):
    """
    Obtener lista de propietarios maestros inactivos
    """
    try:
        propietarios = PropietarioMaestro.objects.filter(activo=False).order_by('nombre_completo')
        
        return Response({
            'count': propietarios.count(),
            'propietarios': PropietarioMaestroSerializer(propietarios, many=True).data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vistas para estadísticas del empleado y su historial de actividades
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def estadisticas_empleado(request):
    """
    Obtener estadísticas específicas del empleado autenticado
    """
    try:
        usuario = request.user
        
        # Fecha actual y rangos de tiempo
        hoy = timezone.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_mes = hoy.replace(day=1)
        inicio_ano = hoy.replace(month=1, day=1)
        
        # Estadísticas de lotes creados por el empleado
        lotes_creados_total = LoteCafe.objects.filter(usuario_registro=usuario).count()
        lotes_creados_hoy = LoteCafe.objects.filter(
            usuario_registro=usuario,
            fecha_creacion__date=hoy
        ).count()
        lotes_creados_semana = LoteCafe.objects.filter(
            usuario_registro=usuario,
            fecha_creacion__date__gte=inicio_semana
        ).count()
        lotes_creados_mes = LoteCafe.objects.filter(
            usuario_registro=usuario,
            fecha_creacion__date__gte=inicio_mes
        ).count()
        
        # Estadísticas de muestras analizadas por el empleado
        muestras_analizadas_total = MuestraCafe.objects.filter(analista=usuario).count()
        muestras_analizadas_hoy = MuestraCafe.objects.filter(
            analista=usuario,
            fecha_analisis__date=hoy
        ).count()
        muestras_analizadas_semana = MuestraCafe.objects.filter(
            analista=usuario,
            fecha_analisis__date__gte=inicio_semana
        ).count()
        muestras_analizadas_mes = MuestraCafe.objects.filter(
            analista=usuario,
            fecha_analisis__date__gte=inicio_mes
        ).count()
        
        # Estadísticas de descargas realizadas por el empleado
        descargas_total = RegistroDescarga.objects.filter(empleado=usuario).count()
        peso_descargado_total = RegistroDescarga.objects.filter(
            empleado=usuario
        ).aggregate(total=Sum('peso_descargado'))['total'] or 0
        
        descargas_hoy = RegistroDescarga.objects.filter(
            empleado=usuario,
            fecha_registro__date=hoy
        ).count()
        peso_descargado_hoy = RegistroDescarga.objects.filter(
            empleado=usuario,
            fecha_registro__date=hoy
        ).aggregate(total=Sum('peso_descargado'))['total'] or 0
        
        descargas_semana = RegistroDescarga.objects.filter(
            empleado=usuario,
            fecha_registro__date__gte=inicio_semana
        ).count()
        peso_descargado_semana = RegistroDescarga.objects.filter(
            empleado=usuario,
            fecha_registro__date__gte=inicio_semana
        ).aggregate(total=Sum('peso_descargado'))['total'] or 0
        
        # Estadísticas de uso de maquinaria por el empleado
        uso_maquinaria_total = RegistroUsoMaquinaria.objects.filter(empleado=usuario).count()
        tiempo_maquinaria_total = RegistroUsoMaquinaria.objects.filter(
            empleado=usuario
        ).aggregate(total=Sum('tiempo_uso_minutos'))['total'] or 0
        
        uso_maquinaria_semana = RegistroUsoMaquinaria.objects.filter(
            empleado=usuario,
            fecha_registro__date__gte=inicio_semana
        ).count()
        tiempo_maquinaria_semana = RegistroUsoMaquinaria.objects.filter(
            empleado=usuario,
            fecha_registro__date__gte=inicio_semana
        ).aggregate(total=Sum('tiempo_uso_minutos'))['total'] or 0
        
        # Estadísticas de resultados de análisis
        muestras_aprobadas = MuestraCafe.objects.filter(
            analista=usuario,
            estado='APROBADA'
        ).count()
        muestras_contaminadas = MuestraCafe.objects.filter(
            analista=usuario,
            estado='CONTAMINADA'
        ).count()
        
        # Calcular porcentajes
        porcentaje_aprobacion = (
            (muestras_aprobadas / muestras_analizadas_total * 100) 
            if muestras_analizadas_total > 0 else 0
        )
        
        # Actividad en bitácora del empleado
        acciones_bitacora_total = RegistroBitacora.objects.filter(usuario=usuario).count()
        acciones_bitacora_hoy = RegistroBitacora.objects.filter(
            usuario=usuario,
            fecha__date=hoy
        ).count()
        
        # Obtener las acciones más frecuentes del empleado
        acciones_frecuentes = RegistroBitacora.objects.filter(
            usuario=usuario
        ).values('accion').annotate(
            total=Count('id')
        ).order_by('-total')[:5]
        
        # Productividad diaria de la última semana
        productividad_semanal = []
        for i in range(7):
            fecha = inicio_semana + timedelta(days=i)
            lotes_dia = LoteCafe.objects.filter(
                usuario_registro=usuario,
                fecha_creacion__date=fecha
            ).count()
            muestras_dia = MuestraCafe.objects.filter(
                analista=usuario,
                fecha_analisis__date=fecha
            ).count()
            descargas_dia = RegistroDescarga.objects.filter(
                empleado=usuario,
                fecha_registro__date=fecha
            ).count()
            
            productividad_semanal.append({
                'fecha': fecha.strftime('%Y-%m-%d'),
                'dia_semana': fecha.strftime('%A'),
                'lotes_creados': lotes_dia,
                'muestras_analizadas': muestras_dia,
                'descargas_realizadas': descargas_dia,
                'total_actividades': lotes_dia + muestras_dia + descargas_dia
            })
        
        return Response({
            'empleado': {
                'id': usuario.id,
                'username': usuario.username,
                'nombre_completo': usuario.get_full_name() or usuario.username,
                'rol': usuario.profile.rol if hasattr(usuario, 'profile') else 'EMPLEADO'
            },
            'lotes_creados': {
                'total': lotes_creados_total,
                'hoy': lotes_creados_hoy,
                'esta_semana': lotes_creados_semana,
                'este_mes': lotes_creados_mes
            },
            'muestras_analizadas': {
                'total': muestras_analizadas_total,
                'hoy': muestras_analizadas_hoy,
                'esta_semana': muestras_analizadas_semana,
                'este_mes': muestras_analizadas_mes,
                'aprobadas': muestras_aprobadas,
                'contaminadas': muestras_contaminadas,
                'porcentaje_aprobacion': round(porcentaje_aprobacion, 1)
            },
            'descargas_realizadas': {
                'total': descargas_total,
                'peso_total': float(peso_descargado_total),
                'hoy': descargas_hoy,
                'peso_hoy': float(peso_descargado_hoy),
                'esta_semana': descargas_semana,
                'peso_semana': float(peso_descargado_semana),
                'este_mes': RegistroDescarga.objects.filter(
                    empleado=usuario,
                    fecha_registro__date__gte=inicio_mes
                ).count()
            },
            'uso_maquinaria': {
                'total_usos': uso_maquinaria_total,
                'tiempo_total_horas': round(tiempo_maquinaria_total / 60, 1) if tiempo_maquinaria_total > 0 else 0,
                'usos_semana': uso_maquinaria_semana,
                'tiempo_semana_horas': round(tiempo_maquinaria_semana / 60, 1) if tiempo_maquinaria_semana > 0 else 0
            },
            'actividad_bitacora': {
                'total_acciones': acciones_bitacora_total,
                'acciones_hoy': acciones_bitacora_hoy,
                'acciones_frecuentes': acciones_frecuentes
            },
            'productividad_semanal': productividad_semanal,
            'fecha_consulta': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response({'error': f'Error al obtener estadísticas: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def historial_actividades_empleado(request):
    """
    Obtener historial detallado de actividades del empleado
    """
    try:
        usuario = request.user
        
        # Obtener descargas realizadas por el empleado con información de insumos
        descargas = RegistroDescarga.objects.filter(empleado=usuario).select_related('lote', 'lote__organizacion', 'insumo').order_by('-fecha_registro')
        
        # Obtener uso de maquinaria del empleado
        uso_maquinaria = RegistroUsoMaquinaria.objects.filter(empleado=usuario).select_related('lote', 'lote__organizacion', 'maquinaria').order_by('-fecha_registro')
        
        # Serializar descargas con información de insumos
        descargas_data = []
        for descarga in descargas:
            descarga_info = {
                'id': descarga.id,
                'lote_numero': descarga.lote.numero_lote,
                'organizacion_nombre': descarga.lote.organizacion.nombre,
                'peso_descargado': float(descarga.peso_descargado),
                'hora_inicio': descarga.hora_inicio,
                'hora_fin': descarga.hora_fin,
                'tiempo_descarga_minutos': descarga.tiempo_descarga_minutos,
                'fecha_registro': descarga.fecha_registro,
                'observaciones': descarga.observaciones or ''
            }
            
            # Agregar información del insumo si existe
            if descarga.insumo:
                descarga_info['insumo'] = {
                    'id': descarga.insumo.id,
                    'nombre': descarga.insumo.nombre,
                    'codigo': descarga.insumo.codigo,
                    'tipo': descarga.insumo.get_tipo_display(),
                    'unidad_medida': descarga.insumo.get_unidad_medida_display()
                }
                if descarga.cantidad_insumo_usado:
                    descarga_info['cantidad_insumo_usado'] = float(descarga.cantidad_insumo_usado)
                else:
                    descarga_info['cantidad_insumo_usado'] = None
            else:
                descarga_info['insumo'] = None
                descarga_info['cantidad_insumo_usado'] = None
                
            descargas_data.append(descarga_info)
        
        # Serializar uso de maquinaria
        maquinaria_data = []
        for uso in uso_maquinaria:
            maquinaria_data.append({
                'id': uso.id,
                'lote_numero': uso.lote.numero_lote,
                'organizacion_nombre': uso.lote.organizacion.nombre,
                'tipo_maquinaria_display': uso.get_tipo_maquinaria_display(),
                'insumo_nombre': uso.maquinaria.nombre if uso.maquinaria else None,
                'insumo_codigo': uso.maquinaria.codigo if uso.maquinaria else None,
                'hora_inicio': uso.hora_inicio,
                'hora_fin': uso.hora_fin,
                'tiempo_uso_minutos': uso.tiempo_uso_minutos,
                'peso_total_descargado': float(uso.peso_total_descargado),
                'fecha_registro': uso.fecha_registro,
                'observaciones': uso.observaciones or ''
            })
        
        return Response({
            'descargas': descargas_data,
            'uso_maquinaria': maquinaria_data
        })
        
    except Exception as e:
        return Response({'error': f'Error al obtener historial: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vista para buscar propietario por cédula
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def buscar_propietario_por_cedula(request, cedula):
    """
    Buscar un propietario en la base de datos maestro por su cédula
    """
    try:
        propietario = PropietarioMaestro.objects.get(cedula=cedula, activo=True)
        return Response({
            'encontrado': True,
            'propietario': PropietarioMaestroSerializer(propietario).data
        })
    except PropietarioMaestro.DoesNotExist:
        return Response({
            'encontrado': False,
            'mensaje': f'No se encontró un propietario con cédula {cedula}'
        })
    except Exception as e:
        return Response({
            'error': f'Error en la búsqueda: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vista para obtener lotes disponibles para descarga
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def lotes_disponibles_descarga(request):
    """
    Obtener lista de lotes que están disponibles para descarga por empleados
    """
    try:
        # Incluir lotes en todas las fases del proceso productivo
        # Estados disponibles para descarga - prácticamente todos los estados excepto los que están pendientes o en proceso inicial
        estados_disponibles = [
            'PENDIENTE',
            'EN_PROCESO', 
            'APROBADO',
            'SEPARACION_PENDIENTE',
            'SEPARACION_APLICADA',
            'LIMPIO',
            'SEPARADO',
            'FINALIZADO'
        ]
        
        lotes = LoteCafe.objects.filter(
            estado__in=estados_disponibles
        ).select_related('organizacion', 'usuario_registro').prefetch_related('propietarios').order_by('-fecha_creacion')
        
        # Serializar los datos
        lotes_data = []
        for lote in lotes:
            # Calcular información de descarga
            peso_descargado_total = lote.descargas.aggregate(
                total=Sum('peso_descargado')
            )['total'] or 0
            
            # Calcular peso pendiente de descarga - usar peso total inicial como referencia base
            peso_total_kg = float(lote.peso_total_final or lote.peso_total_inicial or (lote.total_quintales * 46))  # 46 kg por quintal aprox
            peso_pendiente = peso_total_kg - float(peso_descargado_total)
            porcentaje_descargado = (float(peso_descargado_total) / peso_total_kg * 100) if peso_total_kg > 0 else 0
            
            # Determinar estado de descarga
            estado_descarga = "Disponible"
            if peso_pendiente <= 0:
                estado_descarga = "Completado"
            elif peso_descargado_total > 0:
                estado_descarga = "En progreso"
            
            lote_info = {
                'id': lote.id,
                'numero_lote': lote.numero_lote,
                'organizacion': {
                    'id': lote.organizacion.id,
                    'nombre': lote.organizacion.nombre
                },
                'organizacion_nombre': lote.organizacion.nombre,
                'total_quintales': lote.total_quintales,
                'peso_total_inicial': lote.peso_total_inicial,
                'peso_total_final': lote.peso_total_final,
                'peso_total_kg': peso_total_kg,
                'estado': lote.estado,
                'estado_descarga': estado_descarga,
                'fecha_entrega': lote.fecha_entrega,
                'fecha_creacion': lote.fecha_creacion,
                'observaciones': lote.observaciones,
                'usuario_registro': lote.usuario_registro.get_full_name() or lote.usuario_registro.username,
                'propietarios_count': lote.propietarios.count(),
                # Información específica para descarga
                'peso_descargado': float(peso_descargado_total),
                'peso_pendiente': max(0, peso_pendiente),  # Evitar valores negativos
                'porcentaje_descargado': f"{porcentaje_descargado:.1f}",
                'tiene_descargas': lote.descargas.exists(),
                'ultima_descarga': lote.descargas.order_by('-fecha_registro').first().fecha_registro if lote.descargas.exists() else None,
                'calificacion_final': lote.calificacion_final,
                'fecha_recepcion_final': lote.fecha_recepcion_final,
                'responsable_recepcion_final': lote.responsable_recepcion_final,
                # Información adicional del proceso
                'fecha_limpieza': lote.fecha_limpieza if hasattr(lote, 'fecha_limpieza') else None,
                'responsable_limpieza': lote.responsable_limpieza if hasattr(lote, 'responsable_limpieza') else None,
                'calidad_general': lote.calidad_general if hasattr(lote, 'calidad_general') else None,
                'fecha_separacion': lote.fecha_separacion if hasattr(lote, 'fecha_separacion') else None,
                'responsable_separacion': lote.responsable_separacion if hasattr(lote, 'responsable_separacion') else None
            }
            lotes_data.append(lote_info)
        
        return Response({
            'count': len(lotes_data),
            'results': lotes_data,
            'mensaje': f'Se encontraron {len(lotes_data)} lotes en diferentes fases del proceso disponibles para descarga'
        })
        
    except Exception as e:
        return Response({
            'error': f'Error al obtener lotes disponibles: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def lotes_listos_recepcion_final(request):
    """
    Obtener lista de lotes que están listos para recepción final (estado SEPARADO)
    """
    try:
        # Filtrar solo lotes con estado SEPARADO
        lotes = LoteCafe.objects.filter(estado='SEPARADO').select_related('organizacion', 'usuario_registro').prefetch_related('propietarios').order_by('-fecha_separacion', '-fecha_creacion')
        
        # Serializar los datos
        lotes_data = []
        for lote in lotes:
            lote_info = {
                'id': lote.id,
                'numero_lote': lote.numero_lote,
                'organizacion': {
                    'id': lote.organizacion.id,
                    'nombre': lote.organizacion.nombre
                },
                'organizacion_nombre': lote.organizacion.nombre,
                'total_quintales': lote.total_quintales,
                'estado': lote.estado,
                'fecha_entrega': lote.fecha_entrega,
                'fecha_creacion': lote.fecha_creacion,
                'fecha_separacion': lote.fecha_separacion,
                'responsable_separacion': lote.responsable_separacion,
                'calidad_general': lote.calidad_general,
                'observaciones': lote.observaciones,
                'observaciones_separacion': lote.observaciones_separacion,
                'clasificacion_colores': lote.clasificacion_colores,
                'propietarios': [
                    {
                        'id': prop.id,
                        'nombre_completo': prop.nombre_completo,
                        'cedula': prop.cedula,
                        'quintales_entregados': prop.quintales_entregados,
                        'telefono': prop.telefono,
                        'direccion': prop.direccion
                    }
                    for prop in lote.propietarios.all()
                ]
            }
            lotes_data.append(lote_info)
        
        return Response({
            'count': len(lotes_data),
            'results': lotes_data
        })
        
    except Exception as e:
        return Response({
            'error': f'Error al obtener lotes listos para recepción final: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def procesar_separacion_colores(request):
    """
    Procesar la separación por colores de un lote que ha completado la limpieza
    """
    lote_id = request.data.get('lote_id')
    responsable_separacion = request.data.get('responsable_separacion')
    fecha_separacion = request.data.get('fecha_separacion')
    calidad_general = request.data.get('calidad_general', 'BUENA')
    duracion_proceso = request.data.get('duracion_proceso', 0)
    observaciones_separacion = request.data.get('observaciones_separacion', '')
    clasificacion_colores = request.data.get('clasificacion_colores', {})
    
    # Validaciones básicas
    if not lote_id:
        return Response({'error': 'ID del lote es requerido'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not responsable_separacion:
        return Response({'error': 'Responsable de separación es requerido'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not clasificacion_colores:
        return Response({'error': 'Clasificación por colores es requerida'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        lote = LoteCafe.objects.get(id=lote_id)
        
        # Verificar que el lote esté en estado LIMPIO
        if lote.estado != 'LIMPIO':
            return Response({'error': f'El lote debe estar en estado LIMPIO. Estado actual: {lote.estado}'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar el lote con los datos de separación
        lote.responsable_separacion = responsable_separacion
        lote.fecha_separacion = fecha_separacion
        lote.calidad_general = calidad_general
        lote.duracion_separacion = duracion_proceso
        lote.observaciones_separacion = observaciones_separacion
        lote.clasificacion_colores = clasificacion_colores
        lote.estado = 'SEPARADO'
        lote.save()
        
        # Crear un proceso de análisis para el seguimiento
        proceso_separacion = ProcesoAnalisis.objects.create(
            lote=lote,
            tipo_proceso='SEPARACION',
            usuario_proceso=request.user,
            resultado_general=f'Separación por colores completada. Calidad: {calidad_general}',
            aprobado=True
        )
        
        # Calcular totales para el registro en bitácora
        total_peso_separado = sum(float(datos.get('peso', 0)) for datos in clasificacion_colores.values())
        colores_procesados = [color for color, datos in clasificacion_colores.items() if float(datos.get('peso', 0)) > 0]
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='SEPARACION_COLORES',
            modulo='PROCESOS',
            descripcion=f'Separación por colores completada para lote {lote.numero_lote} - {len(colores_procesados)} colores procesados - Total: {total_peso_separado} kg',
            request=request,
            lote=lote,
            detalles_adicionales={
                'responsable_separacion': responsable_separacion,
                'duracion_proceso': duracion_proceso,
                'calidad_general': calidad_general,
                'colores_procesados': colores_procesados,
                'total_peso_separado': total_peso_separado,
                'clasificacion_completa': clasificacion_colores
            }
        )
        
        return Response({
            'mensaje': 'Separación por colores procesada exitosamente',
            'lote': LoteCafeSerializer(lote).data,
            'proceso_id': proceso_separacion.id
        }, status=status.HTTP_200_OK)
        
    except LoteCafe.DoesNotExist:
        return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error al procesar separación: {str(e)}'}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def enviar_recepcion_final(request):
    """
    Enviar lote a recepción final después de la separación por colores
    """
    lote_id = request.data.get('lote_id')
    responsable_recepcion = request.data.get('responsable_recepcion')
    fecha_recepcion_final = request.data.get('fecha_recepcion_final')
    calificacion_final = request.data.get('calificacion_final', 'A')
    observaciones_finales = request.data.get('observaciones_finales', '')
    
    # Validaciones básicas
    if not lote_id:
        return Response({'error': 'ID del lote es requerido'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not responsable_recepcion:
        return Response({'error': 'Responsable de recepción es requerido'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        lote = LoteCafe.objects.get(id=lote_id)
        
        # Verificar que el lote esté en estado SEPARADO
        if lote.estado != 'SEPARADO':
            return Response({'error': f'El lote debe estar en estado SEPARADO. Estado actual: {lote.estado}'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar el lote con los datos de recepción final
        lote.responsable_recepcion_final = responsable_recepcion
        lote.fecha_recepcion_final = fecha_recepcion_final
        lote.calificacion_final = calificacion_final
        lote.observaciones_finales = observaciones_finales
        lote.estado = 'FINALIZADO'
        lote.save()
        
        # Finalizar el proceso de separación
        proceso_separacion = lote.procesos.filter(tipo_proceso='SEPARACION', fecha_finalizacion__isnull=True).first()
        if proceso_separacion:
            proceso_separacion.fecha_finalizacion = timezone.now()
            proceso_separacion.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='RECEPCION_FINAL',
            modulo='PROCESOS',
            descripcion=f'Lote {lote.numero_lote} enviado a recepción final - Calificación: {calificacion_final} - Responsable: {responsable_recepcion}',
            request=request,
            lote=lote,
            detalles_adicionales={
                'responsable_recepcion': responsable_recepcion,
                'calificacion_final': calificacion_final,
                'observaciones_finales': observaciones_finales
            }
        )
        
        return Response({
            'mensaje': 'Lote enviado a recepción final exitosamente',
            'lote': LoteCafeSerializer(lote).data
        }, status=status.HTTP_200_OK)
        
    except LoteCafe.DoesNotExist:
        return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error al enviar a recepción final: {str(e)}'}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def procesar_limpieza(request):
    """
    Procesar la limpieza de un lote que ha completado el análisis
    """
    from decimal import Decimal
    
    lote_id = request.data.get('lote_id')
    peso_impurezas = request.data.get('peso_impurezas')
    impurezas_encontradas = request.data.get('impurezas_encontradas', '')
    tipo_limpieza = request.data.get('tipo_limpieza', '')
    duracion_limpieza = request.data.get('duracion_limpieza', 0)
    responsable_limpieza = request.data.get('responsable_limpieza', '')
    observaciones_limpieza = request.data.get('observaciones_limpieza', '')
    
    # Validaciones básicas
    if not lote_id:
        return Response({'error': 'ID del lote es requerido'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not peso_impurezas:
        return Response({'error': 'Peso de impurezas es requerido'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Convertir peso_impurezas a Decimal para evitar problemas de tipos
        peso_impurezas = Decimal(str(peso_impurezas))
        if peso_impurezas < 0:
            return Response({'error': 'El peso de impurezas no puede ser negativo'}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({'error': 'El peso de impurezas debe ser un número válido'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        lote = LoteCafe.objects.get(id=lote_id)
        
        # Verificar que el lote esté en estado que permite limpieza
        estados_permitidos = ['APROBADO', 'SEPARACION_APLICADA']
        if lote.estado not in estados_permitidos:
            return Response({'error': f'El lote debe estar en estado APROBADO o SEPARACION_APLICADA. Estado actual: {lote.estado}'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Calcular peso después de limpieza - usar Decimal para todos los cálculos
        peso_antes_limpieza = lote.peso_total_final or lote.peso_total_inicial or Decimal('0')
        peso_antes_limpieza = Decimal(str(peso_antes_limpieza))  # Asegurar que es Decimal
        
        peso_despues_limpieza = peso_antes_limpieza - peso_impurezas
        
        # Validar que el peso después de limpieza sea positivo
        if peso_despues_limpieza <= 0:
            return Response({'error': 'El peso de impurezas no puede ser mayor al peso total del lote'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar el lote con los datos de limpieza
        lote.fecha_limpieza = timezone.now()
        lote.responsable_limpieza = responsable_limpieza
        lote.peso_impurezas = peso_impurezas
        lote.impurezas_encontradas = impurezas_encontradas
        lote.tipo_limpieza = tipo_limpieza
        lote.duracion_limpieza = duracion_limpieza
        lote.observaciones_limpieza = observaciones_limpieza
        lote.peso_total_final = peso_despues_limpieza
        lote.estado = 'LIMPIO'  # Listo para separación por colores
        lote.save()
        
        # Crear un proceso de análisis para el seguimiento
        proceso_limpieza = ProcesoAnalisis.objects.create(
            lote=lote,
            tipo_proceso='LIMPIEZA',
            usuario_proceso=request.user,
            resultado_general=f'Limpieza completada. Impurezas removidas: {peso_impurezas} kg. Tipo: {tipo_limpieza}',
            aprobado=True
        )
        
        # Calcular porcentaje de impurezas
        porcentaje_impurezas = (peso_impurezas / peso_antes_limpieza * 100) if peso_antes_limpieza > 0 else Decimal('0')
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='PROCESAR_LIMPIEZA',
            modulo='PROCESOS',
            descripcion=f'Limpieza completada para lote {lote.numero_lote} - Impurezas: {peso_impurezas} kg ({porcentaje_impurezas:.1f}%) - Tipo: {tipo_limpieza} - Responsable: {responsable_limpieza}',
            request=request,
            lote=lote,
            detalles_adicionales={
                'peso_antes_limpieza': float(peso_antes_limpieza),
                'peso_impurezas_removidas': float(peso_impurezas),
                'peso_despues_limpieza': float(peso_despues_limpieza),
                'porcentaje_impurezas': float(porcentaje_impurezas),
                'tipo_limpieza': tipo_limpieza,
                'duracion_limpieza': duracion_limpieza,
                'responsable_limpieza': responsable_limpieza,
                'impurezas_encontradas': impurezas_encontradas
            }
        )
        
        return Response({
            'mensaje': 'Limpieza procesada exitosamente',
            'lote': LoteCafeSerializer(lote).data,
            'proceso_id': proceso_limpieza.id,
            'detalles_proceso': {
                'peso_antes_limpieza': float(peso_antes_limpieza),
                'peso_impurezas_removidas': float(peso_impurezas),
                'peso_despues_limpieza': float(peso_despues_limpieza),
                'porcentaje_impurezas': f"{porcentaje_impurezas:.1f}%"
            }
        }, status=status.HTTP_200_OK)
        
    except LoteCafe.DoesNotExist:
        return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error al procesar limpieza: {str(e)}'}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def enviar_parte_limpia_limpieza(request, lote_id):
    """
    Enviar la parte limpia de un lote con separación inteligente aplicada al proceso de limpieza.
    Este endpoint maneja la merma de quintales separando definitivamente los propietarios contaminados.
    """
    from decimal import Decimal
    
    try:
        lote = LoteCafe.objects.get(id=lote_id)
        
        # Verificar que el lote esté en estado que permite esta operación
        estados_permitidos = ['SEPARACION_APLICADA', 'SEPARACION_PENDIENTE']
        if lote.estado not in estados_permitidos:
            return Response({
                'error': f'El lote debe estar en estado SEPARACION_APLICADA o SEPARACION_PENDIENTE. Estado actual: {lote.estado}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener muestras iniciales y de segundo muestreo
        muestras_iniciales = lote.muestras.filter(es_segundo_muestreo=False)
        muestras_segundo = lote.muestras.filter(es_segundo_muestreo=True)
        
        # Identificar propietarios que deben ser separados (contaminados confirmados)
        propietarios_a_separar = []
        propietarios_limpios = []
        
        for propietario in lote.propietarios.all():
            muestra_inicial = muestras_iniciales.filter(propietario=propietario).first()
            muestra_segundo = muestras_segundo.filter(propietario=propietario).first()
            
            if muestra_inicial and muestra_inicial.estado == 'CONTAMINADA':
                if muestra_segundo:
                    # Hay segundo muestreo, usar ese resultado
                    if muestra_segundo.estado == 'CONTAMINADA':
                        propietarios_a_separar.append(propietario)
                    else:
                        propietarios_limpios.append(propietario)
                else:
                    # No hay segundo muestreo, se considera contaminado
                    propietarios_a_separar.append(propietario)
            else:
                # Muestra inicial aprobada
                propietarios_limpios.append(propietario)
        
        # Calcular quintales que se van a separar
        quintales_originales = lote.total_quintales
        quintales_separados = sum(prop.quintales_entregados for prop in propietarios_a_separar)
        quintales_limpios = sum(prop.quintales_entregados for prop in propietarios_limpios)
        
        # Validar que los cálculos sean consistentes
        if quintales_separados + quintales_limpios != quintales_originales:
            return Response({
                'error': 'Error en el cálculo de quintales. Los quintales no suman correctamente.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if quintales_limpios <= 0:
            return Response({
                'error': 'No hay quintales limpios para enviar a limpieza.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear un registro histórico de la separación antes de modificar
        observaciones_separacion = f"""SEPARACIÓN INTELIGENTE APLICADA - {lote.observaciones}

PROPIETARIOS SEPARADOS ({len(propietarios_a_separar)} propietarios - {quintales_separados} qq):
{chr(10).join([f'• {prop.nombre_completo} ({prop.cedula}): {prop.quintales_entregados} qq' for prop in propietarios_a_separar])}

PROPIETARIOS QUE CONTINÚAN ({len(propietarios_limpios)} propietarios - {quintales_limpios} qq):
{chr(10).join([f'• {prop.nombre_completo} ({prop.cedula}): {prop.quintales_entregados} qq' for prop in propietarios_limpios])}

RESUMEN DE SEPARACIÓN:
- Quintales originales: {quintales_originales} qq
- Quintales separados: {quintales_separados} qq ({round((quintales_separados/quintales_originales)*100, 1)}%)
- Quintales que continúan: {quintales_limpios} qq ({round((quintales_limpios/quintales_originales)*100, 1)}%)"""
        
        # Marcar propietarios separados como inactivos (no los eliminamos para mantener historial)
        for propietario in propietarios_a_separar:
            # Agregar un campo para marcar como separado
            propietario.observaciones = f"SEPARADO POR CONTAMINACIÓN - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            propietario.save()
        
        # Actualizar el lote con los nuevos totales
        lote.total_quintales = quintales_limpios
        lote.observaciones = observaciones_separacion
        lote.estado = 'APROBADO'  # Ahora puede ir a limpieza
        
        # Ajustar el peso total si existe
        if lote.peso_total_inicial:
            # Calcular proporción de peso que se mantiene
            proporcion_limpia = Decimal(str(quintales_limpios)) / Decimal(str(quintales_originales))
            lote.peso_total_inicial = lote.peso_total_inicial * proporcion_limpia
        
        if lote.peso_total_final:
            proporcion_limpia = Decimal(str(quintales_limpios)) / Decimal(str(quintales_originales))
            lote.peso_total_final = lote.peso_total_final * proporcion_limpia
        
        lote.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='SEPARACION_INTELIGENTE',
            modulo='PROCESOS',
            descripcion=f'Separación inteligente aplicada al lote {lote.numero_lote} - {quintales_separados} qq separados, {quintales_limpios} qq enviados a limpieza',
            request=request,
            lote=lote,
            detalles_adicionales={
                'quintales_originales': float(quintales_originales),
                'quintales_separados': float(quintales_separados),
                'quintales_limpios': float(quintales_limpios),
                'porcentaje_salvado': float(round((quintales_limpios/quintales_originales)*100, 1)),
                'propietarios_separados': len(propietarios_a_separar),
                'propietarios_limpios': len(propietarios_limpios),
                'propietarios_incluidos': [
                    {
                        'nombre': prop.nombre_completo,
                        'cedula': prop.cedula,
                        'quintales': float(prop.quintales_entregados)
                    } for prop in propietarios_limpios
                ]
            }
        )
        
        return Response({
            'mensaje': 'Separación inteligente aplicada exitosamente. Parte limpia enviada a limpieza.',
            'detalles': {
                'quintales_originales': float(quintales_originales),
                'quintales_separados': float(quintales_separados),
                'quintales_enviados_limpieza': float(quintales_limpios),
                'porcentaje_salvado': round((quintales_limpios/quintales_originales)*100, 1),
                'propietarios_separados': len(propietarios_a_separar),
                'propietarios_aprobados': len(propietarios_limpios),
                'propietarios_incluidos': [
                    {
                        'nombre': prop.nombre_completo,
                        'cedula': prop.cedula,
                        'quintales': float(prop.quintales_entregados)
                    } for prop in propietarios_limpios
                ]
            },
            'lote': LoteCafeSerializer(lote).data
        }, status=status.HTTP_200_OK)
        
    except LoteCafe.DoesNotExist:
        return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error al procesar separación inteligente: {str(e)}'}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vista para crear tareas con insumos
class TareaInsumoListCreateView(generics.ListCreateAPIView):
    serializer_class = TareaInsumoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['descripcion', 'empleado__username', 'insumo__nombre', 'muestra__numero_muestra', 'lote__numero_lote']
    ordering_fields = ['fecha_creacion', 'empleado__username', 'insumo__nombre']
    ordering = ['-fecha_creacion']
    filterset_fields = ['empleado', 'insumo', 'muestra', 'lote', 'resultado_analisis']
    
    def get_queryset(self):
        """Obtener tareas con información relacionada"""
        return TareaInsumo.objects.select_related(
            'empleado', 'insumo', 'muestra', 'lote'
        ).all()
    
    def perform_create(self, serializer):
        tarea = serializer.save()
        
        # Registrar en bitácora
        insumo_info = f"{tarea.insumo.nombre} ({tarea.insumo.codigo})"
        contexto_info = ""
        
        if tarea.muestra:
            contexto_info = f" - Muestra: {tarea.muestra.numero_muestra}"
        elif tarea.lote:
            contexto_info = f" - Lote: {tarea.lote.numero_lote}"
        
        cantidad_info = ""
        if tarea.cantidad:
            cantidad_info = f" - Cantidad: {tarea.cantidad} {tarea.insumo.get_unidad_medida_display()}"
        
        tiempo_info = ""
        if tarea.tiempo_uso:
            tiempo_info = f" - Tiempo: {tarea.tiempo_uso} min"
        
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='REGISTRAR_TAREA_INSUMO',
            modulo='PROCESOS',
            descripcion=f'Tarea con insumo registrada: {insumo_info}{contexto_info}{cantidad_info}{tiempo_info} - {tarea.descripcion[:100]}{"..." if len(tarea.descripcion) > 100 else ""}',
            request=self.request,
            lote=tarea.lote,
            muestra=tarea.muestra,
            detalles_adicionales={
                'tarea_id': tarea.id,
                'insumo_id': tarea.insumo.id,
                'insumo_nombre': tarea.insumo.nombre,
                'insumo_tipo': tarea.insumo.get_tipo_display(),
                'cantidad_utilizada': float(tarea.cantidad) if tarea.cantidad else None,
                'tiempo_uso_minutos': tarea.tiempo_uso,
                'peso_usado_kg': float(tarea.peso_usado) if tarea.peso_usado else None,
                'resultado_analisis': tarea.resultado_analisis,
                'descripcion_completa': tarea.descripcion
            }
        )

class TareaInsumoDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TareaInsumo.objects.all()
    serializer_class = TareaInsumoSerializer
    permission_classes = [permissions.IsAuthenticated]

# Vistas para Procesos de Producción
class ProcesoListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear procesos de producción"""
    queryset = Proceso.objects.all().order_by('-fecha_inicio')
    serializer_class = ProcesoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['numero', 'nombre', 'descripcion', 'responsable__username', 'responsable__first_name', 'responsable__last_name']
    ordering_fields = ['fecha_inicio', 'estado', 'fase_actual', 'progreso']
    ordering = ['-fecha_inicio']
    filterset_fields = ['estado', 'fase_actual', 'responsable', 'activo']
    
    def perform_create(self, serializer):
        proceso = serializer.save()
        
        # ✅ CORRECCIÓN: Cambiar estado de los lotes a "EN_PROCESO" - INCLUIR SEPARACION_APLICADA
        lotes_ids = self.request.data.get('lotes', [])
        if lotes_ids:
            # Incluir tanto lotes APROBADO como SEPARACION_APLICADA
            estados_validos = ['APROBADO', 'SEPARACION_APLICADA']
            lotes = LoteCafe.objects.filter(id__in=lotes_ids, estado__in=estados_validos)
            
            # Verificar que se encontraron lotes
            if not lotes.exists():
                # Log de debugging para identificar el problema
                lotes_solicitados = LoteCafe.objects.filter(id__in=lotes_ids)
                estados_encontrados = [f"{lote.numero_lote}: {lote.estado}" for lote in lotes_solicitados]
                print(f"❌ DEBUG: No se encontraron lotes válidos para el proceso")
                print(f"   - Lotes solicitados: {lotes_ids}")
                print(f"   - Estados encontrados: {estados_encontrados}")
                print(f"   - Estados válidos: {estados_validos}")
            else:
                # ✅ CORRECCIÓN PRINCIPAL: Primero agregar los lotes al proceso
                proceso.lotes.set(lotes)
                
                # Luego cambiar el estado de cada lote
                for lote in lotes:
                    lote.estado = 'EN_PROCESO'
                    lote.save()
                    print(f"✅ Lote {lote.numero_lote} agregado al proceso y estado cambiado a EN_PROCESO")
                
                # Calcular totales basado en los lotes
                proceso.calcular_totales()
                
                # Verificar que los lotes se agregaron correctamente
                print(f"✅ Proceso {proceso.id} creado con {proceso.lotes.count()} lotes")
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='INICIAR_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Proceso de producción creado: {proceso.numero} - {proceso.nombre} - {proceso.total_lotes} lotes incluidos',
            request=self.request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'numero_proceso': proceso.numero,
                'lotes_incluidos': [lote.numero_lote for lote in proceso.lotes.all()],
                'responsable': proceso.responsable.get_full_name() or proceso.responsable.username,
                'quintales_totales': proceso.quintales_totales,
                'peso_inicial': float(proceso.peso_total_inicial) if proceso.peso_total_inicial else None,
                'estados_lotes_incluidos': estados_validos
            }
        )

class ProcesoDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para obtener, actualizar y eliminar procesos específicos"""
    queryset = Proceso.objects.all()
    serializer_class = ProcesoSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_update(self, serializer):
        proceso_anterior = self.get_object()
        proceso = serializer.save()
        
        # Recalcular totales si se modificaron los lotes
        if 'lotes' in self.request.data:
            proceso.calcular_totales()
        
        # Registrar cambios en bitácora
        cambios = []
        if proceso_anterior.estado != proceso.estado:
            cambios.append(f'Estado: {proceso_anterior.estado} → {proceso.estado}')
        if proceso_anterior.fase_actual != proceso.fase_actual:
            cambios.append(f'Fase: {proceso_anterior.fase_actual} → {proceso.fase_actual}')
        if proceso_anterior.responsable != proceso.responsable:
            cambios.append(f'Responsable: {proceso_anterior.responsable.username} → {proceso.responsable.username}')
        
        if cambios:
            RegistroBitacora.registrar_accion(
                usuario=self.request.user,
                accion='ACTUALIZAR_PROCESO',
                modulo='PROCESOS',
                descripcion=f'Proceso actualizado: {proceso.numero} - {", ".join(cambios)}',
                request=self.request,
                detalles_adicionales={
                    'proceso_id': proceso.id,
                    'cambios': cambios
                }
            )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def avanzar_fase_proceso(request, proceso_id):
    """Avanzar un proceso a la siguiente fase"""
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        
        if proceso.avanzar_fase():
            # Registrar en bitácora
            RegistroBitacora.registrar_accion(
                usuario=request.user,
                accion='AVANZAR_FASE',
                modulo='PROCESOS',
                descripcion=f'Proceso {proceso.numero} avanzó a fase {proceso.fase_actual} - Progreso: {proceso.progreso}%',
                request=request,
                detalles_adicionales={
                    'proceso_id': proceso.id,
                    'fase_nueva': proceso.fase_actual,
                    'progreso': proceso.progreso,
                    'estado': proceso.estado
                }
            )
            
            return Response({
                'mensaje': f'Proceso avanzado a fase {proceso.fase_actual}',
                'proceso': ProcesoSerializer(proceso).data
            })
        else:
            return Response({
                'error': 'No se pudo avanzar la fase del proceso'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def finalizar_fase_proceso(request, proceso_id):
    """Finalizar una fase específica del proceso"""
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        fase = request.data.get('fase')
        
        if not fase:
            return Response({'error': 'La fase es requerida'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar que la fase sea válida
        fases_validas = [choice[0] for choice in Proceso.FASES_PROCESO]
        if fase not in fases_validas:
            return Response({'error': 'Fase inválida'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar progreso basado en la fase
        proceso.fase_actual = fase
        proceso.progreso = proceso.porcentaje_progreso
        
        if fase == 'FINALIZADO':
            proceso.estado = 'COMPLETADO'
            proceso.fecha_fin_real = timezone.now()
            
            # Cambiar estado de los lotes a FINALIZADO
            for lote in proceso.lotes.all():
                lote.estado = 'FINALIZADO'
                lote.save()
        
        proceso.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='FINALIZAR_FASE',
            modulo='PROCESOS',
            descripcion=f'Fase {fase} finalizada para proceso {proceso.numero} - Progreso: {proceso.progreso}%',
            request=request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'fase_finalizada': fase,
                'progreso': proceso.progreso,
                'estado': proceso.estado
            }
        )
        
        return Response({
            'mensaje': f'Fase {fase} finalizada exitosamente',
            'proceso': ProcesoSerializer(proceso).data
        })
        
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Vistas para Tareas de Proceso
class TareaProcesoListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear tareas de proceso"""
    serializer_class = TareaProcesoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['descripcion', 'proceso__numero', 'empleado__username', 'resultado']
    ordering_fields = ['fecha_registro', 'fecha_ejecucion', 'completada']
    ordering = ['-fecha_registro']
    filterset_fields = ['proceso', 'tipo_tarea', 'fase', 'empleado', 'completada']
    
    def get_queryset(self):
        queryset = TareaProceso.objects.all()
        
        # Filtrar por proceso si se proporciona en los parámetros
        proceso_id = self.request.query_params.get('proceso_id')
        if proceso_id:
            queryset = queryset.filter(proceso_id=proceso_id)
        
        return queryset.select_related('proceso', 'empleado')
    
    def perform_create(self, serializer):
        tarea = serializer.save()
        
        # Calcular duración si se proporcionaron horas
        if tarea.hora_inicio and tarea.hora_fin:
            tarea.calcular_duracion()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='CREAR_TAREA_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Tarea creada para proceso {tarea.proceso.numero} - {tarea.get_tipo_tarea_display()} - Fase: {tarea.fase}',
            request=self.request,
            detalles_adicionales={
                'tarea_id': tarea.id,
                'proceso_id': tarea.proceso.id,
                'tipo_tarea': tarea.tipo_tarea,
                'fase': tarea.fase,
                'duracion_minutos': tarea.duracion_minutos,
                'peso_impurezas_encontradas': float(tarea.peso_impurezas_encontradas) if tarea.peso_impurezas_encontradas else None,
                'peso_impurezas_removidas': float(tarea.peso_impurezas_removidas) if tarea.peso_impurezas_removidas else None
            }
        )

class TareaProcesoDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para obtener, actualizar y eliminar tareas específicas"""
    queryset = TareaProceso.objects.all()
    serializer_class = TareaProcesoSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_update(self, serializer):
        tarea = serializer.save()
        
        # Recalcular duración si se modificaron las horas
        if tarea.hora_inicio and tarea.hora_fin:
            tarea.calcular_duracion()
        
        # Registrar actualización en bitácora
        RegistroBitacora.registrar_accion(
            usuario=self.request.user,
            accion='ACTUALIZAR_TAREA_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Tarea actualizada: {tarea.proceso.numero} - {tarea.get_tipo_tarea_display()}',
            request=self.request,
            detalles_adicionales={
                'tarea_id': tarea.id,
                'proceso_id': tarea.proceso.id,
                'completada': tarea.completada
            }
        )

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def estadisticas_procesos_produccion(request):
    """Obtener estadísticas generales de procesos de producción"""
    try:
        # Estadísticas básicas
        total_procesos = Proceso.objects.count()
        procesos_activos = Proceso.objects.filter(activo=True).count()
        procesos_iniciados = Proceso.objects.filter(estado='INICIADO').count()
        procesos_en_proceso = Proceso.objects.filter(estado='EN_PROCESO').count()
        procesos_completados = Proceso.objects.filter(estado='COMPLETADO').count()
        procesos_cancelados = Proceso.objects.filter(estado='CANCELADO').count()
        
        # Estadísticas por fase
        fases_stats = []
        for fase_id, fase_nombre in Proceso.FASES_PROCESO:
            count = Proceso.objects.filter(fase_actual=fase_id, activo=True).count()
            fases_stats.append({
                'fase': fase_id,
                'nombre': fase_nombre,
                'cantidad': count
            })
        
        # Procesos por responsable (top 10)
        responsables_stats = Proceso.objects.values(
            'responsable__username', 
            'responsable__first_name', 
            'responsable__last_name'
        ).annotate(
            total_procesos=Count('id'),
            procesos_completados=Count('id', filter=Q(estado='COMPLETADO'))
        ).order_by('-total_procesos')[:10]
        
        # Estadísticas de tareas
        total_tareas = TareaProceso.objects.count()
        tareas_completadas = TareaProceso.objects.filter(completada=True).count()
        tareas_pendientes = total_tareas - tareas_completadas
        
        # Tareas por tipo
        tipos_tarea_stats = TareaProceso.objects.values('tipo_tarea').annotate(
            total=Count('id'),
            completadas=Count('id', filter=Q(completada=True))
        ).order_by('-total')
        
        return Response({
            'procesos': {
                'total': total_procesos,
                'activos': procesos_activos,
                'iniciados': procesos_iniciados,
                'en_proceso': procesos_en_proceso,
                'completados': procesos_completados,
                'cancelados': procesos_cancelados
            },
            'fases_stats': fases_stats,
            'responsables_stats': responsables_stats,
            'tareas': {
                'total': total_tareas,
                'completadas': tareas_completadas,
                'pendientes': tareas_pendientes
            },
            'tipos_tarea_stats': tipos_tarea_stats
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def lotes_disponibles_para_proceso(request):
    """Obtener lotes que están disponibles para crear procesos (estado APROBADO o SEPARACION_APLICADA)"""
    try:
        # ✅ INCLUIR LOTES CON SEPARACIÓN APLICADA
        # Estos lotes han completado el análisis y tienen su parte limpia lista para procesar
        estados_disponibles = ['APROBADO', 'SEPARACION_APLICADA']
        
        lotes = LoteCafe.objects.filter(
            estado__in=estados_disponibles
        ).select_related('organizacion').prefetch_related('propietarios').order_by('-fecha_creacion')
        
        lotes_data = []
        for lote in lotes:
            # Información adicional para lotes con separación aplicada
            info_separacion = ""
            if lote.estado == 'SEPARACION_APLICADA':
                info_separacion = " (Separación inteligente aplicada - Parte limpia disponible)"
            
            lote_info = {
                'id': lote.id,
                'numero_lote': lote.numero_lote,
                'organizacion': {
                    'id': lote.organizacion.id,
                    'nombre': lote.organizacion.nombre
                },
                'organizacion_nombre': lote.organizacion.nombre,
                'total_quintales': lote.total_quintales,
                'estado': lote.estado,
                'estado_display': 'Aprobado' if lote.estado == 'APROBADO' else 'Separación Aplicada',
                'fecha_entrega': lote.fecha_entrega,
                'fecha_creacion': lote.fecha_creacion,
                'peso_total_inicial': float(lote.peso_total_inicial) if lote.peso_total_inicial else None,
                'peso_total_final': float(lote.peso_total_final) if lote.peso_total_final else None,
                'observaciones': lote.observaciones,
                'propietarios_count': lote.propietarios.count(),
                'info_adicional': info_separacion,
                'tiene_separacion_aplicada': lote.estado == 'SEPARACION_APLICADA',
                'propietarios': [
                    {
                        'id': prop.id,
                        'nombre_completo': prop.nombre_completo,
                        'cedula': prop.cedula,
                        'quintales_entregados': float(prop.quintales_entregados)
                    }
                    for prop in lote.propietarios.all()
                ]
            }
            lotes_data.append(lote_info)
        
        return Response({
            'count': len(lotes_data),
            'lotes': lotes_data,
            'mensaje': f'Se encontraron {len(lotes_data)} lotes disponibles para procesos de producción',
            'estados_incluidos': estados_disponibles
        })
        
    except Exception as e:
        return Response({
            'error': f'Error al obtener lotes disponibles: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ✅ NUEVAS VISTAS PARA GUARDAR DATOS DE FORMULARIOS DE PROCESO

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def guardar_datos_pilado(request, proceso_id):
    """
    Vista para guardar los datos del formulario de pilado en la base de datos
    """
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        
        # Extraer datos del formulario
        datos_pilado = {
            'tipo_impureza_encontrada': request.data.get('tipo_impureza_encontrada', ''),
            'peso_impurezas_removidas': request.data.get('peso_impurezas_removidas', ''),
            'observaciones': request.data.get('observaciones', ''),
            'tareas_realizadas': {
                'canteado': request.data.get('tareas_realizadas', {}).get('canteado', False),
                'tiempo_canteado': request.data.get('tareas_realizadas', {}).get('tiempo_canteado', ''),
                'interno': request.data.get('tareas_realizadas', {}).get('interno', False)
            },
            'fecha_guardado': timezone.now().isoformat(),
            'usuario_registro': request.user.get_full_name() or request.user.username
        }
        
        # Guardar en el proceso
        proceso.datos_pilado = datos_pilado
        proceso.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='FINALIZAR_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Datos de pilado guardados para proceso {proceso.numero}',
            request=request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'fase': 'PILADO',
                'datos_guardados': datos_pilado
            }
        )
        
        return Response({
            'mensaje': 'Datos de pilado guardados exitosamente',
            'proceso_id': proceso.id,
            'datos_guardados': datos_pilado
        }, status=status.HTTP_200_OK)
        
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def guardar_datos_clasificacion(request, proceso_id):
    """
    Vista para guardar los datos del formulario de clasificación en la base de datos
    """
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        
        # Extraer datos del formulario
        datos_clasificacion = {
            'numero_malla_ocupada': request.data.get('numero_malla_ocupada', ''),
            'peso_cafe_caracolillo': request.data.get('peso_cafe_caracolillo', ''),
            'peso_cafe_exportacion': request.data.get('peso_cafe_exportacion', ''),
            'observaciones': request.data.get('observaciones', ''),
            'fecha_guardado': timezone.now().isoformat(),
            'usuario_registro': request.user.get_full_name() or request.user.username
        }
        
        # Guardar en el proceso
        proceso.datos_clasificacion = datos_clasificacion
        proceso.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='FINALIZAR_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Datos de clasificación guardados para proceso {proceso.numero}',
            request=request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'fase': 'CLASIFICACION',
                'datos_guardados': datos_clasificacion
            }
        )
        
        return Response({
            'mensaje': 'Datos de clasificación guardados exitosamente',
            'proceso_id': proceso.id,
            'datos_guardados': datos_clasificacion
        }, status=status.HTTP_200_OK)
        
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def guardar_datos_densidad_1(request, proceso_id):
    """
    Vista para guardar los datos del formulario de densidad (primera parte) en la base de datos
    """
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        
        # Extraer datos del formulario
        datos_densidad_1 = {
            'peso_cafe_densidad_1': request.data.get('peso_cafe_densidad_1', ''),
            'observaciones_densidad_1': request.data.get('observaciones_densidad_1', ''),
            'fecha_guardado': timezone.now().isoformat(),
            'usuario_registro': request.user.get_full_name() or request.user.username
        }
        
        # Guardar en el proceso
        proceso.datos_densidad_1 = datos_densidad_1
        proceso.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='FINALIZAR_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Datos de densidad (parte 1) guardados para proceso {proceso.numero}',
            request=request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'fase': 'DENSIDAD_1',
                'datos_guardados': datos_densidad_1
            }
        )
        
        return Response({
            'mensaje': 'Datos de densidad (parte 1) guardados exitosamente',
            'proceso_id': proceso.id,
            'datos_guardados': datos_densidad_1
        }, status=status.HTTP_200_OK)
        
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def guardar_datos_densidad_2(request, proceso_id):
    """
    Vista para guardar los datos del formulario de densimetría 2 en la base de datos
    """
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        
        # Extraer datos del formulario
        datos_densidad_2 = {
            'peso_cafe_densidad_2': request.data.get('peso_cafe_densidad_2', ''),
            'observaciones_densidad_2': request.data.get('observaciones_densidad_2', ''),
            'fecha_guardado': timezone.now().isoformat(),
            'usuario_registro': request.user.get_full_name() or request.user.username
        }
        
        # Guardar en el proceso
        proceso.datos_densidad_2 = datos_densidad_2
        proceso.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='FINALIZAR_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Datos de densimetría 2 guardados para proceso {proceso.numero}',
            request=request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'fase': 'DENSIDAD_2',
                'datos_guardados': datos_densidad_2
            }
        )
        
        return Response({
            'mensaje': 'Datos de densimetría 2 guardados exitosamente',
            'proceso_id': proceso.id,
            'datos_guardados': datos_densidad_2
        }, status=status.HTTP_200_OK)
        
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def guardar_datos_color(request, proceso_id):
    """
    Vista para guardar los datos del formulario de separación por color en la base de datos
    """
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        
        # Extraer datos del formulario
        datos_color = {
            'responsable_separacion': request.data.get('responsable_separacion', ''),
            'fecha_separacion': request.data.get('fecha_separacion', ''),
            'calidad_general': request.data.get('calidad_general', 'BUENA'),
            'duracion_proceso': request.data.get('duracion_proceso', ''),
            'observaciones_separacion': request.data.get('observaciones_separacion', ''),
            'clasificacion_colores': request.data.get('clasificacion_colores', {}),
            'fecha_guardado': timezone.now().isoformat(),
            'usuario_registro': request.user.get_full_name() or request.user.username
        }
        
        # Guardar en el proceso
        proceso.datos_color = datos_color
        proceso.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='SEPARACION_COLORES',
            modulo='PROCESOS',
            descripcion=f'Datos de separación por color guardados para proceso {proceso.numero}',
            request=request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'fase': 'COLOR',
                'datos_guardados': datos_color
            }
        )
        
        return Response({
            'mensaje': 'Datos de separación por color guardados exitosamente',
            'proceso_id': proceso.id,
            'datos_guardados': datos_color
        }, status=status.HTTP_200_OK)
        
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def guardar_datos_empaquetado(request, proceso_id):
    """
    Vista para guardar los datos del formulario de empaquetado en la base de datos
    """
    try:
        proceso = Proceso.objects.get(id=proceso_id)
        
        # Extraer datos del formulario
        datos_empaquetado = {
            'cafe_caracolillo': request.data.get('cafe_caracolillo', ''),
            'cafe_descarte': request.data.get('cafe_descarte', ''),
            'cafe_exportacion': request.data.get('cafe_exportacion', ''),
            'observaciones_empaquetado': request.data.get('observaciones_empaquetado', ''),
            'fecha_guardado': timezone.now().isoformat(),
            'usuario_registro': request.user.get_full_name() or request.user.username
        }
        
        # Guardar en el proceso
        proceso.datos_empaquetado = datos_empaquetado
        proceso.save()
        
        # Registrar en bitácora
        RegistroBitacora.registrar_accion(
            usuario=request.user,
            accion='FINALIZAR_PROCESO',
            modulo='PROCESOS',
            descripcion=f'Datos de empaquetado guardados para proceso {proceso.numero}',
            request=request,
            detalles_adicionales={
                'proceso_id': proceso.id,
                'fase': 'EMPAQUE',
                'datos_guardados': datos_empaquetado
            }
        )
        
        return Response({
            'mensaje': 'Datos de empaquetado guardados exitosamente',
            'proceso_id': proceso.id,
            'datos_guardados': datos_empaquetado
        }, status=status.HTTP_200_OK)
        
    except Proceso.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
