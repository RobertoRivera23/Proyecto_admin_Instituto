# facturacion/management/commands/recordatorios_pago.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from web.models import Notificacion, Alumno, CuotaAlumno, TipoNotificacion
from django.contrib.auth.models import User
from datetime import timedelta

class Command(BaseCommand):
    help = 'Envía recordatorios suaves de pago antes del vencimiento'
    
    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        
        # Obtener tipo de notificación para recordatorios
        tipo_notificacion, _ = TipoNotificacion.objects.get_or_create(
            nombre='Recordatorios',
            defaults={'descripcion': 'Recordatorios de pagos próximos a vencer'}
        )
        
        # Cuotas que vencen en 3 días
        fecha_proximo_vencimiento = hoy + timedelta(days=3)
        
        cuotas_proximas = CuotaAlumno.objects.filter(
            pagada=False,
            fecha_vencimiento=fecha_proximo_vencimiento,
            alumno__activo=True
        )
        
        notificaciones_creadas = 0
        
        for cuota in cuotas_proximas:
            # Crear notificación para el alumno (si tiene usuario asociado)
            if cuota.alumno.usuario:
                Notificacion.objects.create(
                    titulo='📅 Recordatorio de pago próximo',
                    mensaje=(
                        f'Estimado {cuota.alumno.nombre_completo()},\n\n'
                        f'Le recordamos que el pago de la cuota correspondiente a '
                        f'{cuota.mes}/{cuota.año} por un monto de ${cuota.monto} '
                        f'vencerá el {cuota.fecha_vencimiento}.\n\n'
                        f'Por favor, realice el pago a tiempo para evitar moras.'
                    ),
                    usuario_destino=cuota.alumno.usuario,
                    tipo=tipo_notificacion,
                    prioridad='BAJA',
                    relacion_alumno=cuota.alumno,
                    relacion_cuota=cuota
                )
                notificaciones_creadas += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Recordatorios enviados: {notificaciones_creadas}'
        ))