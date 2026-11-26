# web/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.management import call_command
from web.models import Notificacion, Alumno, CuotaAlumno, TipoNotificacion
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

@shared_task(name='generar_notificaciones_mora_task')
def generar_notificaciones_mora_task(dias_retraso=5):
    """
    Tarea Celery para generar notificaciones de mora
    Basada en tu management command existente
    """
    try:
        hoy = timezone.now().date()
        fecha_limite_mora = hoy - timezone.timedelta(days=dias_retraso)
        
        # Obtener tipo de notificación
        tipo_mora, created = TipoNotificacion.objects.get_or_create(
            codigo='MORA_PAGOS',
            defaults={
                'nombre': 'Mora de Pagos',
                'descripcion': 'Notificaciones automáticas de alumnos con pagos en mora',
                'prioridad': 'ALTA',
                'color': 'danger',
                'icono': 'fa-exclamation-triangle',
                'ES_MANUAL': False
            }
        )
        
        # Obtener coordinadores
        coordinadores = User.objects.filter(
            groups__name__in=['Coordinadores', 'Administradores']
        ).distinct()
        
        if not coordinadores.exists():
            logger.warning('No hay coordinadores configurados para notificaciones de mora')
            return {'status': 'warning', 'message': 'No hay coordinadores configurados'}
        
        # Consulta de alumnos en mora
        alumnos_mora = Alumno.objects.filter(
            cuotaalumno__pagada=False,
            cuotaalumno__fecha_vencimiento__lt=fecha_limite_mora,
            activo=True
        ).distinct()
        
        notificaciones_creadas = 0
        
        for alumno in alumnos_mora:
            # Verificar si ya hay notificación reciente
            notificacion_reciente = Notificacion.objects.filter(
                tipo=tipo_mora,
                relacion_alumno=alumno,
                fecha_creacion__gte=hoy - timezone.timedelta(days=3),
                eliminada=False
            ).exists()
            
            if not notificacion_reciente:
                # Obtener cuotas vencidas
                cuotas_vencidas = CuotaAlumno.objects.filter(
                    alumno=alumno,
                    pagada=False,
                    fecha_vencimiento__lt=hoy
                ).order_by('fecha_vencimiento')
                
                if cuotas_vencidas.exists():
                    dias_de_retraso = (hoy - cuotas_vencidas.first().fecha_vencimiento).days
                    monto_total = sum(cuota.monto for cuota in cuotas_vencidas)
                    
                    # Determinar prioridad
                    if dias_de_retraso > 30 or monto_total > 1000:
                        prioridad = 'URGENTE'
                    elif dias_de_retraso > 15:
                        prioridad = 'ALTA'
                    elif dias_de_retraso > 7:
                        prioridad = 'MEDIA'
                    else:
                        prioridad = 'BAJA'
                    
                    # Crear notificaciones para cada coordinador
                    for coordinador in coordinadores:
                        Notificacion.objects.create(
                            usuario_destino=coordinador,
                            usuario_origen=None,
                            tipo=tipo_mora,
                            titulo=f'⚠️ MORA: {alumno.nombre_completo()} - ${monto_total:,.2f}',
                            mensaje=(
                                f'El alumno {alumno.nombre_completo()} tiene '
                                f'{cuotas_vencidas.count()} cuota(s) vencida(s) '
                                f'por un total de ${monto_total:,.2f}.\n\n'
                                f'**Días de retraso:** {dias_de_retraso} días\n'
                                f'**Contacto:** {alumno.telefono or "No registrado"}\n'
                                f'**Email:** {alumno.email or "No registrado"}'
                            ),
                            estado='PENDIENTE',
                            prioridad=prioridad,
                            es_manual=False,
                            relacion_alumno=alumno,
                            fecha_vencimiento=hoy + timezone.timedelta(days=7)
                        )
                        notificaciones_creadas += 1
        
        logger.info(f'Tarea de notificaciones de mora completada: {notificaciones_creadas} notificaciones creadas')
        return {
            'status': 'success',
            'notificaciones_creadas': notificaciones_creadas,
            'alumnos_procesados': alumnos_mora.count()
        }
        
    except Exception as e:
        logger.error(f'Error en tarea de notificaciones de mora: {str(e)}')
        return {'status': 'error', 'message': str(e)}

@shared_task(name='enviar_recordatorios_pago_task')
def enviar_recordatorios_pago_task():
    """
    Tarea para enviar recordatorios de pago automáticos
    """
    try:
        hoy = timezone.now().date()
        fecha_proximo_vencimiento = hoy + timezone.timedelta(days=3)
        
        # Obtener tipo de notificación
        tipo_recordatorio, _ = TipoNotificacion.objects.get_or_create(
            codigo='RECORDATORIO_PAGO',
            defaults={
                'nombre': 'Recordatorio de Pago',
                'descripcion': 'Recordatorios automáticos de pagos próximos a vencer',
                'prioridad': 'MEDIA',
                'color': 'warning',
                'icono': 'fa-calendar-check',
                'ES_MANUAL': False
            }
        )
        
        # Cuotas que vencen en 3 días
        cuotas_proximas = CuotaAlumno.objects.filter(
            pagada=False,
            fecha_vencimiento=fecha_proximo_vencimiento,
            alumno__activo=True
        ).select_related('alumno')
        
        notificaciones_creadas = 0
        
        for cuota in cuotas_proximas:
            if hasattr(cuota.alumno, 'usuario') and cuota.alumno.usuario:
                # Verificar si ya hay notificación reciente
                notificacion_reciente = Notificacion.objects.filter(
                    tipo=tipo_recordatorio,
                    relacion_cuota=cuota,
                    fecha_creacion__gte=hoy - timezone.timedelta(days=2),
                    eliminada=False
                ).exists()
                
                if not notificacion_reciente:
                    Notificacion.objects.create(
                        usuario_destino=cuota.alumno.usuario,
                        usuario_origen=None,
                        tipo=tipo_recordatorio,
                        titulo='📅 Recordatorio de pago próximo',
                        mensaje=(
                            f'Estimado {cuota.alumno.nombre_completo()},\n\n'
                            f'Le recordamos que el pago de la cuota correspondiente a '
                            f'{cuota.mes}/{cuota.año} por un monto de **${cuota.monto:,.2f}** '
                            f'vencerá el **{cuota.fecha_vencimiento.strftime("%d/%m/%Y")}**.\n\n'
                            f'Por favor, realice el pago a tiempo para evitar cargos por mora.'
                        ),
                        estado='PENDIENTE',
                        prioridad='BAJA',
                        es_manual=False,
                        relacion_alumno=cuota.alumno,
                        relacion_cuota=cuota,
                        fecha_vencimiento=cuota.fecha_vencimiento
                    )
                    notificaciones_creadas += 1
        
        logger.info(f'Tarea de recordatorios completada: {notificaciones_creadas} recordatorios enviados')
        return {
            'status': 'success',
            'recordatorios_enviados': notificaciones_creadas
        }
        
    except Exception as e:
        logger.error(f'Error en tarea de recordatorios: {str(e)}')
        return {'status': 'error', 'message': str(e)}

@shared_task(name='generar_reporte_semanal_moras_task')
def generar_reporte_semanal_moras_task():
    """
    Tarea para generar reporte semanal de moras
    """
    try:
        # Puedes mantener tu lógica actual del command
        # o integrarla aquí directamente
        from django.core.management import call_command
        
        # Ejecutar el command existente
        call_command('reporte_semanal_moras')
        
        logger.info('Reporte semanal de moras generado')
        return {'status': 'success', 'message': 'Reporte generado'}
        
    except Exception as e:
        logger.error(f'Error generando reporte semanal: {str(e)}')
        return {'status': 'error', 'message': str(e)}

@shared_task(name='ejecutar_comando_management')
def ejecutar_comando_management(nombre_comando, *args, **kwargs):
    """
    Tarea genérica para ejecutar cualquier command de management
    Útil para mantener compatibilidad con tus commands existentes
    """
    try:
        from django.core.management import call_command
        call_command(nombre_comando, *args, **kwargs)
        return {'status': 'success', 'comando': nombre_comando}
    except Exception as e:
        logger.error(f'Error ejecutando comando {nombre_comando}: {str(e)}')
        return {'status': 'error', 'message': str(e)}