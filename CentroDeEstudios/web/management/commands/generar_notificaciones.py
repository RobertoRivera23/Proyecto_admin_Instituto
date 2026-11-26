# management/commands/generar_notificaciones.py
from django.core.management.base import BaseCommand
from web.services.notificaciones_service import ServicioNotificaciones
from web.models import Notificacion

class Command(BaseCommand):
    help = 'Genera notificaciones automáticas del sistema'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando generación de notificaciones automáticas...')
        
        # Crear tipos de notificación si no existen
        ServicioNotificaciones.crear_tipos_notificacion()
        self.stdout.write('✅ Tipos de notificación verificados')
        
        # Generar todas las notificaciones automáticas
        count_antes = Notificacion.objects.count()
        ServicioNotificaciones.generar_notificaciones_automaticas()
        count_despues = Notificacion.objects.count()
        
        self.stdout.write(f'✅ Notificaciones generadas: {count_despues - count_antes} nuevas')
        
        # Limpiar notificaciones antiguas
        archivadas = ServicioNotificaciones.limpiar_notificaciones_antiguas()
        self.stdout.write(f'✅ Notificaciones archivadas: {archivadas}')
        
        self.stdout.write(
            self.style.SUCCESS('Proceso de notificaciones completado correctamente')
        )
        
        
