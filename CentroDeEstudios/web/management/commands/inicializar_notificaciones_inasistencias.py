from django.core.management.base import BaseCommand
from web.models import TipoNotificacion, Personal
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Inicializa tipo de notificación para inasistencias consecutivas'
    
    def handle(self, *args, **options):
        # Crear tipo de notificación
        tipo, created = TipoNotificacion.objects.get_or_create(
            codigo='INASISTENCIA_CONSECUTIVA',
            defaults={
                'nombre': 'Inasistencias Consecutivas',
                'descripcion': 'Notificación automática cuando un alumno tiene 2 inasistencias consecutivas',
                'prioridad': 'ALTA',
                'color': 'danger',
                'icono': 'fa-user-times',
                'ES_MANUAL': False
            }
        )
        
        if created:
            # Asignar a todos los auxiliares, coordinadores y administradores
            personal_relevante = Personal.objects.filter(
                tipo__in=['AUXILIAR', 'COORDINADOR', 'ADMINISTRADOR'],
                activo=True,
                eliminado=False
            )
            
            # Verificar si el campo PUEDE_ASIGNAR existe
            if hasattr(tipo, 'PUEDE_ASIGNAR'):
                tipo.PUEDE_ASIGNAR.set(personal_relevante)
            
            self.stdout.write(self.style.SUCCESS(
                f'✅ Tipo de notificación creado: {tipo.nombre}'
            ))
            
            # Mostrar quiénes pueden recibir estas notificaciones
            if personal_relevante.exists():
                self.stdout.write("👥 Pueden recibir notificaciones:")
                for p in personal_relevante:
                    self.stdout.write(f"   - {p.nombre_completo()} ({p.tipo})")
            else:
                self.stdout.write("⚠️ No se encontró personal para asignar")
        else:
            self.stdout.write(f'ℹ️ Tipo de notificación ya existente: {tipo.nombre}')