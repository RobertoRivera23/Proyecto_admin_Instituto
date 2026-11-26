from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from web.models import Curso
from web.utils import verificar_inasistencias_consecutivas

class Command(BaseCommand):
    help = 'Verifica inasistencias consecutivas en todos los cursos activos'
    
    def handle(self, *args, **options):
        hoy = timezone.now().date()
        
        # Obtener cursos activos que tienen clase hoy
        cursos_activos = Curso.objects.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
            auxiliar__isnull=False  # Solo cursos con auxiliar
        )
        
        self.stdout.write(f"🔍 Verificando {cursos_activos.count()} cursos activos...")
        
        total_notificaciones = 0
        
        for curso in cursos_activos:
            try:
                # Verificar si hoy es día de clase para este curso
                dias_clase = curso.obtener_dias_lista()
                dia_hoy = hoy.strftime('%A').upper()
                
                # Mapeo de días en español (ajusta según tu configuración)
                dias_espanol = {
                    'MONDAY': 'LUNES',
                    'TUESDAY': 'MARTES',
                    'WEDNESDAY': 'MIÉRCOLES',
                    'THURSDAY': 'JUEVES',
                    'FRIDAY': 'VIERNES',
                    'SATURDAY': 'SÁBADO',
                    'SUNDAY': 'DOMINGO'
                }
                
                dia_hoy_es = dias_espanol.get(dia_hoy, '')
                
                # Verificar si hoy es día de clase
                if dia_hoy_es in [d.upper() for d in dias_clase]:
                    count = verificar_inasistencias_consecutivas(curso.id, hoy)
                    total_notificaciones += count
                    
                    if count > 0:
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✅ Curso {curso.nombre}: {count} notificaciones"
                        ))
                    else:
                        self.stdout.write(f"  ✓ Curso {curso.nombre}: 0 notificaciones")
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ❌ Error en curso {curso.nombre}: {e}"
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Verificación completada. Total notificaciones: {total_notificaciones}'
        ))