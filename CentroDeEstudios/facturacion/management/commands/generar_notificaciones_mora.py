# facturacion/management/commands/generar_notificaciones_mora.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from web.models import Notificacion, Alumno, CuotaAlumno, TipoNotificacion, Personal
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q, Min
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Genera notificaciones automáticas para alumnos en mora'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dias-retraso',
            type=int,
            default=5,
            help='Número de días de retraso para considerar mora'
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Modo prueba: solo muestra lo que haría sin crear notificaciones'
        )
    
    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        dias_retraso = kwargs['dias_retraso']
        modo_test = kwargs['test']
        
        # 1. Obtener el tipo de notificación para mora
        try:
            tipo_mora = TipoNotificacion.objects.get(codigo='MORA_PAGOS')
        except TipoNotificacion.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Tipo de notificación MORA_PAGOS no encontrado. '
                'Ejecuta crear_tipos_notificacion_pagos() primero.'
            ))
            return
        
        # 2. Obtener usuarios que deben recibir notificaciones de mora
        # Basado en el campo PUEDE_ASIGNAR del TipoNotificacion
        usuarios_destino = User.objects.filter(
            personal__in=tipo_mora.PUEDE_ASIGNAR.all(),
            is_active=True
        ).distinct()
        
        if not usuarios_destino.exists():
            self.stdout.write(self.style.WARNING(
                '⚠️ No se encontraron usuarios configurados para recibir notificaciones de mora'
            ))
            return
        
        # 3. Calcular fecha límite para considerar mora
        fecha_limite_mora = hoy - timedelta(days=dias_retraso)
        
        # 4. Alumnos con cuotas vencidas por más de X días
        alumnos_mora = Alumno.objects.filter(
            cuotaalumno__pagada=False,
            cuotaalumno__fecha_vencimiento__lt=fecha_limite_mora,
            activo=True
        ).annotate(
            total_cuotas_vencidas=Count('cuotaalumno', 
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            monto_total_vencido=Sum('cuotaalumno__monto',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            primera_cuota_vencida=Min('cuotaalumno__fecha_vencimiento',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            )
        ).filter(total_cuotas_vencidas__gt=0).distinct()
        
        notificaciones_a_crear = 0
        alumnos_procesados = 0
        
        for alumno in alumnos_mora:
            alumnos_procesados += 1
            
            # Obtener cuotas vencidas específicas
            cuotas_vencidas = CuotaAlumno.objects.filter(
                alumno=alumno,
                pagada=False,
                fecha_vencimiento__lt=hoy
            ).order_by('fecha_vencimiento')
            
            # Calcular días de retraso para la cuota más antigua
            dias_de_retraso = (hoy - alumno.primera_cuota_vencida).days
            
            # 5. Verificar si ya hay notificaciones recientes para este alumno
            # Evitar spam de notificaciones
            notificacion_reciente = Notificacion.objects.filter(
                tipo=tipo_mora,
                relacion_alumno=alumno,
                fecha_creacion__gte=hoy - timedelta(days=3),  # Últimos 3 días
                eliminada=False
            ).exists()
            
            if notificacion_reciente:
                continue  # Saltar si ya hay notificación reciente
            
            # 6. Detalles de las cuotas vencidas
            detalles_cuotas = []
            for cuota in cuotas_vencidas[:5]:  # Mostrar máximo 5 cuotas
                dias_vencida = (hoy - cuota.fecha_vencimiento).days
                detalles_cuotas.append(
                    f"• {cuota.mes}/{cuota.año}: ${cuota.monto:,.2f} "
                    f"(Vencida hace {dias_vencida} días)"
                )
            
            if cuotas_vencidas.count() > 5:
                detalles_cuotas.append(f"• ...y {cuotas_vencidas.count() - 5} cuotas más")
            
            detalles_texto = "\n".join(detalles_cuotas)
            
            # 7. Determinar prioridad basada en días de retraso y monto
            if dias_de_retraso > 30 or (alumno.monto_total_vencido or 0) > 1000:
                prioridad = 'URGENTE'
            elif dias_de_retraso > 15 or (alumno.monto_total_vencido or 0) > 500:
                prioridad = 'ALTA'
            elif dias_de_retraso > 7:
                prioridad = 'MEDIA'
            else:
                prioridad = 'BAJA'
            
            # 8. Crear mensaje detallado
            mensaje = f"""
📋 **ALUMNO EN MORA** 📋

**Alumno:** {alumno.nombre_completo()}
**Matrícula:** {alumno.matricula or 'N/A'}
**Días de retraso:** {dias_de_retraso} días
**Total adeudado:** ${alumno.monto_total_vencido or 0:,.2f}
**Cuotas vencidas:** {alumno.total_cuotas_vencidas}

**Detalle de cuotas vencidas:**
{detalles_texto}

**Información de contacto:**
• Teléfono: {alumno.telefono or 'No registrado'}
• Email: {alumno.email or 'No registrado'}
• Contacto de emergencia: {alumno.contacto_emergencia_nombre or 'No registrado'}
• Tel. emergencia: {alumno.contacto_emergencia_telefono or 'No registrado'}

**Acciones sugeridas:**
1. Contactar al alumno o contacto de emergencia
2. Revisar historial de pagos
3. Verificar si hay acuerdo de pago pendiente
"""
            
            # 9. Crear notificaciones para cada usuario destino
            if not modo_test:
                for usuario in usuarios_destino:
                    Notificacion.objects.create(
                        usuario_destino=usuario,
                        usuario_origen=None,  # Sistema
                        tipo=tipo_mora,
                        titulo=f'⚠️ MORA: {alumno.nombre_completo()} - ${alumno.monto_total_vencido or 0:,.2f}',
                        mensaje=mensaje.strip(),
                        estado='PENDIENTE',
                        prioridad=prioridad,
                        es_manual=False,  # Automática
                        fecha_vencimiento=hoy + timedelta(days=7),  # Vencer en 7 días
                        relacion_alumno=alumno
                    )
                    notificaciones_a_crear += 1
            
            # Log detallado
            logger.info(
                f'Notificación de mora generada para {alumno.nombre_completo()}: '
                f'{alumno.total_cuotas_vencidas} cuotas vencidas, '
                f'${alumno.monto_total_vencido or 0:.2f}, '
                f'{dias_de_retraso} días de retraso'
            )
        
        # 10. Resumen
        if modo_test:
            self.stdout.write(self.style.WARNING(
                f'🔍 MODO PRUEBA - No se crearon notificaciones\n'
                f'   • Alumnos en mora detectados: {alumnos_mora.count()}\n'
                f'   • Alumnos procesados: {alumnos_procesados}\n'
                f'   • Notificaciones a crear: {alumnos_procesados * usuarios_destino.count()}\n'
                f'   • Usuarios destino: {usuarios_destino.count()}\n'
                f'   • Días de retraso mínimo: {dias_retraso}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Notificaciones de mora generadas:\n'
                f'   • Alumnos en mora: {alumnos_mora.count()}\n'
                f'   • Notificaciones creadas: {notificaciones_a_crear}\n'
                f'   • Usuarios notificados: {usuarios_destino.count()}\n'
                f'   • Días de retraso considerado: {dias_retraso} días'
            ))