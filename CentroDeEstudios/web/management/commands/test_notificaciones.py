# web/management/commands/test_notificaciones.py
from django.core.management.base import BaseCommand
from web.services.notificaciones_service import ServicioNotificaciones
from web.models import Notificacion, User

class Command(BaseCommand):
    help = 'Probar el sistema de notificaciones'

    def handle(self, *args, **options):
        self.stdout.write('🧪 Probando sistema de notificaciones...')
        
        # Crear tipos de notificación
        ServicioNotificaciones.crear_tipos_notificacion()
        self.stdout.write('✅ Tipos de notificación creados')
        
        # Generar notificaciones automáticas
        ServicioNotificaciones.generar_notificaciones_automaticas()
        self.stdout.write('✅ Notificaciones automáticas generadas')
        
        # Contar notificaciones
        total = Notificacion.objects.count()
        pendientes = Notificacion.objects.filter(estado='PENDIENTE').count()
        
        self.stdout.write(f'📊 Estadísticas:')
        self.stdout.write(f'   - Total notificaciones: {total}')
        self.stdout.write(f'   - Pendientes: {pendientes}')
        
        # Mostrar algunas notificaciones
        notificaciones = Notificacion.objects.all()[:5]
        self.stdout.write('\n📋 Últimas notificaciones:')
        for notif in notificaciones:
            self.stdout.write(f'   - {notif.titulo} (Origen: {notif.usuario_origen})')