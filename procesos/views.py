from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from django.utils import timezone
from .models import Organizacion, Lote, Muestra
from .serializers import OrganizacionSerializer, LoteSerializer, MuestraSerializer
import json

class OrganizacionViewSet(viewsets.ModelViewSet):
    queryset = Organizacion.objects.all()
    serializer_class = OrganizacionSerializer
    permission_classes = [IsAuthenticated]

class LoteViewSet(viewsets.ModelViewSet):
    queryset = Lote.objects.all()
    serializer_class = LoteSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Lote.objects.filter(usuario_creador=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(usuario_creador=self.request.user)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def crear_con_propietarios(request):
    try:
        data = request.data.copy()
        print(f"Datos recibidos: {data}")
        
        # Extraer propietarios del payload
        propietarios_data = data.get('propietarios', [])
        print(f"Propietarios recibidos: {propietarios_data}")
        
        if not propietarios_data:
            return Response({
                'error': 'Se requiere al menos un propietario'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar que los propietarios tengan los campos requeridos
        for i, propietario in enumerate(propietarios_data):
            if not propietario.get('nombre_completo'):
                return Response({
                    'error': f'El propietario {i+1} requiere nombre completo'
                }, status=status.HTTP_400_BAD_REQUEST)
            if not propietario.get('cedula'):
                return Response({
                    'error': f'El propietario {i+1} requiere cédula'
                }, status=status.HTTP_400_BAD_REQUEST)
            if not propietario.get('quintales_entregados'):
                return Response({
                    'error': f'El propietario {i+1} requiere quintales entregados'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Preparar datos del lote
        lote_data = {
            'codigo': data.get('codigo'),
            'organizacion': data.get('organizacion'),
            'cantidad_quintales': data.get('cantidad_quintales'),
            'fecha_cosecha': data.get('fecha_cosecha'),
            'observaciones': data.get('observaciones', ''),
            'propietarios': json.dumps(propietarios_data)  # Convertir a JSON string
        }
        
        print(f"Datos del lote preparados: {lote_data}")
        
        # Validar con el serializer
        serializer = LoteSerializer(data=lote_data, context={'request': request})
        if serializer.is_valid():
            lote = serializer.save()
            
            # Crear respuesta con datos del lote creado
            response_data = LoteSerializer(lote).data
            # Deserializar propietarios para la respuesta
            response_data['propietarios'] = json.loads(lote.propietarios)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            print(f"Errores de validación: {serializer.errors}")
            return Response({
                'error': 'Datos inválidos',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except json.JSONDecodeError as e:
        return Response({
            'error': 'Error al procesar datos JSON',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error inesperado: {str(e)}")
        return Response({
            'error': 'Error interno del servidor',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MuestraViewSet(viewsets.ModelViewSet):
    queryset = Muestra.objects.all()
    serializer_class = MuestraSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Muestra.objects.filter(lote__usuario_creador=self.request.user)
    
    @action(detail=False, methods=['post'])
    def seleccionar(self, request):
        lote_id = request.data.get('lote_id')
        muestras_data = request.data.get('muestras', [])
        
        try:
            lote = Lote.objects.get(id=lote_id, usuario_creador=request.user)
            
            # Crear las muestras
            for muestra_data in muestras_data:
                Muestra.objects.create(
                    lote=lote,
                    codigo_muestra=muestra_data['codigo_muestra'],
                    peso_gramos=muestra_data['peso_gramos']
                )
            
            # Cambiar estado del lote a análisis
            lote.estado = 'analisis'
            lote.save()
            
            return Response({'message': 'Muestras seleccionadas exitosamente'})
        except Lote.DoesNotExist:
            return Response({'error': 'Lote no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def resultado(self, request, pk=None):
        try:
            muestra = self.get_object()
            data = request.data
            
            muestra.humedad = data.get('humedad')
            muestra.defectos = data.get('defectos')
            muestra.puntaje_taza = data.get('puntaje_taza')
            muestra.observaciones = data.get('observaciones', '')
            muestra.fecha_resultado = timezone.now()
            muestra.estado = 'completada'
            muestra.save()
            
            # Verificar si todas las muestras del lote están completadas
            lote = muestra.lote
            muestras_pendientes = Muestra.objects.filter(
                lote=lote, 
                estado__in=['pendiente', 'en_analisis']
            ).count()
            
            if muestras_pendientes == 0:
                lote.estado = 'finalizado'
                lote.save()
            
            return Response({
                'message': 'Resultado registrado exitosamente',
                'lote_estado': lote.estado
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Vista para estadísticas
from rest_framework.views import APIView

class EstadisticasView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Estadísticas básicas
        total_lotes = Lote.objects.filter(usuario_creador=user).count()
        total_organizaciones = Organizacion.objects.count()
        total_muestras = Muestra.objects.filter(lote__usuario_creador=user).count()
        
        # Lotes por estado
        lotes_por_estado = Lote.objects.filter(usuario_creador=user).values('estado').annotate(
            cantidad=Count('id')
        )
        
        # Muestras por estado
        muestras_por_estado = Muestra.objects.filter(lote__usuario_creador=user).values('estado').annotate(
            cantidad=Count('id')
        )
        
        return Response({
            'totales': {
                'lotes': total_lotes,
                'organizaciones': total_organizaciones,
                'muestras': total_muestras
            },
            'lotes_por_estado': list(lotes_por_estado),
            'muestras_por_estado': list(muestras_por_estado)
        })
