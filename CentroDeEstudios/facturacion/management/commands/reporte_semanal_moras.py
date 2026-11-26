# facturacion/management/commands/reporte_semanal_moras.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from web.models import Alumno, CuotaAlumno, TipoNotificacion, Notificacion, Personal
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from datetime import timedelta
from django.template.loader import render_to_string

class Command(BaseCommand):
    help = 'Genera reporte semanal de moras y envía a coordinadores'
    
    def handle(self, *args, **kwargs):
        hoy = timezone.now().date()
        inicio_semana = hoy - timedelta(days=7)
        
        # Obtener tipo de notificación para reportes
        tipo_reporte, _ = TipoNotificacion.objects.get_or_create(
            codigo='REPORTE_MORAS',
            defaults={
                'nombre': 'Reporte de Moras',
                'descripcion': 'Reportes semanales de moras de pagos',
                'prioridad': 'MEDIA',
                'color': 'info',
                'icono': 'fa-chart-bar',
                'ES_MANUAL': False
            }
        )
        
        # Estadísticas de la semana
        estadisticas = {
            'total_alumnos_mora': Alumno.objects.filter(
                cuotaalumno__pagada=False,
                cuotaalumno__fecha_vencimiento__lt=hoy,
                activo=True
            ).distinct().count(),
            
            'total_monto_vencido': CuotaAlumno.objects.filter(
                pagada=False,
                fecha_vencimiento__lt=hoy
            ).aggregate(total=Sum('monto'))['total'] or 0,
            
            'nuevos_en_mora_esta_semana': Alumno.objects.filter(
                cuotaalumno__pagada=False,
                cuotaalumno__fecha_vencimiento__lt=hoy,
                cuotaalumno__fecha_vencimiento__gte=inicio_semana,
                activo=True
            ).distinct().count(),
            
            'cuotas_vencidas_esta_semana': CuotaAlumno.objects.filter(
                pagada=False,
                fecha_vencimiento__lt=hoy,
                fecha_vencimiento__gte=inicio_semana
            ).count(),
            
            'alumnos_con_mas_30_dias': Alumno.objects.filter(
                cuotaalumno__pagada=False,
                cuotaalumno__fecha_vencimiento__lt=hoy - timedelta(days=30),
                activo=True
            ).distinct().count(),
        }
        
        # Obtener top 10 alumnos con mayor deuda
        top_deudores = Alumno.objects.filter(
            cuotaalumno__pagada=False,
            cuotaalumno__fecha_vencimiento__lt=hoy,
            activo=True
        ).annotate(
            total_deuda=Sum('cuotaalumno__monto',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            ),
            cuotas_vencidas=Count('cuotaalumno',
                filter=Q(cuotaalumno__pagada=False) & 
                Q(cuotaalumno__fecha_vencimiento__lt=hoy)
            )
        ).filter(total_deuda__gt=0).order_by('-total_deuda')[:10]
        
        # Obtener coordinadores
        coordinadores = User.objects.filter(
            personal__tipo='COORDINADOR',
            personal__activo=True,
            personal__eliminado=False,
            is_active=True
        ).distinct()
        
        # Crear reporte para cada coordinador
        for coordinador in coordinadores:
            mensaje = f"""
📊 **REPORTE SEMANAL DE MORAS** 📊
**Período:** {inicio_semana} al {hoy}
**Generado:** {hoy.strftime('%d/%m/%Y %H:%M')}

📈 **ESTADÍSTICAS PRINCIPALES:**
• Total alumnos en mora: {estadisticas['total_alumnos_mora']}
• Monto total vencido: ${estadisticas['total_monto_vencido']:,.2f}
• Nuevos en mora esta semana: {estadisticas['nuevos_en_mora_esta_semana']}
• Cuotas vencidas esta semana: {estadisticas['cuotas_vencidas_esta_semana']}
• Alumnos con más de 30 días: {estadisticas['alumnos_con_mas_30_dias']}

🏆 **TOP 10 DEUDORES:**
"""
            
            # Agregar lista de top deudores
            for i, alumno in enumerate(top_deudores, 1):
                mensaje += f"\n{i}. **{alumno.nombre_completo()}** - "
                mensaje += f"${alumno.total_deuda:,.2f} ({alumno.cuotas_vencidas} cuotas)"
            
            mensaje += f"""

📋 **ACCIONES RECOMENDADAS:**
1. Contactar a los 5 principales deudores
2. Revisar alumnos con más de 30 días de mora
3. Actualizar acuerdos de pago pendientes
4. Programar seguimiento para la próxima semana

🔗 **ACCESOS RÁPIDOS:**
• Lista completa de morosos: /admin/web/alumno/?mora=true
• Reporte detallado: /facturacion/reportes/moras/
• Dashboard: /notificaciones/dashboard/
"""
            
            Notificacion.objects.create(
                usuario_destino=coordinador,
                usuario_origen=None,
                tipo=tipo_reporte,
                titulo=f'📊 Reporte Semanal de Moras - {hoy}',
                mensaje=mensaje.strip(),
                estado='PENDIENTE',
                prioridad='MEDIA',
                es_manual=False
            )
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ Reporte semanal generado y enviado a {coordinadores.count()} coordinadores'
        ))