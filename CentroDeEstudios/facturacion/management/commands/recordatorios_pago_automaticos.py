# facturacion/management/commands/recordatorios_pago_automaticos.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from web.models import Notificacion, Alumno, CuotaAlumno, TipoNotificacion
from datetime import timedelta

class Command(BaseCommand):
    help = 'Envía recordatorios automáticos de pagos próximos a vencer'
    
    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        
        # Obtener tipo de notificación para recordatorios
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
        fecha_proximo_vencimiento = hoy + timedelta(days=3)
        
        cuotas_proximas = CuotaAlumno.objects.filter(
            pagada=False,
            fecha_vencimiento=fecha_proximo_vencimiento,
            alumno__activo=True
        ).select_related('alumno')
        
        notificaciones_creadas = 0
        
        for cuota in cuotas_proximas:
            # Verificar si el alumno tiene usuario asociado
            if hasattr(cuota.alumno, 'usuario') and cuota.alumno.usuario:
                # Verificar si ya hay notificación reciente
                notificacion_reciente = Notificacion.objects.filter(
                    tipo=tipo_recordatorio,
                    relacion_cuota=cuota,
                    fecha_creacion__gte=hoy - timedelta(days=2),
                    eliminada=False
                ).exists()
                
                if not notificacion_reciente:
                    Notificacion.objects.create(
                        usuario_destino=cuota.alumno.usuario,
                        usuario_origen=None,  # Sistema
                        tipo=tipo_recordatorio,
                        titulo='📅 Recordatorio de pago próximo',
                        mensaje=(
                            f'Estimado {cuota.alumno.nombre_completo()},\n\n'
                            f'Le recordamos que el pago de la cuota correspondiente a '
                            f'{cuota.mes}/{cuota.año} por un monto de **${cuota.monto:,.2f}** '
                            f'vencerá el **{cuota.fecha_vencimiento.strftime("%d/%m/%Y")}**.\n\n'
                            f'Por favor, realice el pago a tiempo para evitar cargos por mora.\n\n'
                            f'**Métodos de pago disponibles:**\n'
                            f'• Transferencia bancaria\n'
                            f'• Efectivo en administración\n'
                            f'• Tarjeta de crédito/débito\n\n'
                            f'Gracias por su atención.'
                        ),
                        estado='PENDIENTE',
                        prioridad='BAJA',
                        es_manual=False,
                        relacion_alumno=cuota.alumno,
                        relacion_cuota=cuota,
                        fecha_vencimiento=cuota.fecha_vencimiento
                    )
                    notificaciones_creadas += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Recordatorios enviados: {notificaciones_creadas}'
        ))