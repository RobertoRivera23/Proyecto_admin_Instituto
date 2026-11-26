# facturacion/management/commands/programar_notificaciones.py
from django.core.management.base import BaseCommand
from django_crontab.crontab import Crontab

class Command(BaseCommand):
    help = 'Programa las tareas automáticas de notificaciones'
    
    def handle(self, *args, **kwargs):
        crontab = Crontab()
        
        # Agregar tarea diaria de notificaciones de mora (a las 9 AM)
        crontab.add_job(
            '9 * * *',
            'python manage.py generar_notificaciones_mora --dias-retraso 5',
            'Notificaciones de mora diarias'
        )
        
        # Agregar tarea de recordatorios (a las 10 AM)
        crontab.add_job(
            '10 * * *',
            'python manage.py recordatorios_pago',
            'Recordatorios de pagos próximos'
        )
        
        # Agregar reporte semanal (lunes a las 8 AM)
        crontab.add_job(
            '0 8 * * 1',
            'python manage.py generar_reporte_moras_semanal',
            'Reporte semanal de moras'
        )
        
        self.stdout.write(self.style.SUCCESS(
            '✅ Tareas programadas exitosamente:\n'
            '1. Notificaciones de mora: Diario a las 9 AM\n'
            '2. Recordatorios de pago: Diario a las 10 AM\n'
            '3. Reporte semanal: Lunes a las 8 AM'
        ))