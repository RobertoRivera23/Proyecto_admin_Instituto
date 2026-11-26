# web/services/notificaciones_service.py
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count, Avg
from django.contrib.auth.models import User, Group

# Importar tus modelos - usa las importaciones correctas según tu estructura
from web.models import Curso, Inscripcion, Asistencia, Alumno, Notificacion, TipoNotificacion, HistorialNotificacion
from facturacion.models import Pago 

class ServicioNotificaciones:
    
    @staticmethod
    def crear_tipos_notificacion():
        """Crear los tipos de notificación por defecto"""
        tipos = [
            {
                'nombre': 'Curso por Iniciar',
                'codigo': 'CURSO_POR_INICIAR',
                'descripcion': 'Notificación para cursos que están por iniciar',
                'prioridad': 'ALTA',
                'color': 'warning',
                'icono': 'fa-calendar-plus'
            },
            {
                'nombre': 'Curso por Finalizar',
                'codigo': 'CURSO_POR_FINALIZAR', 
                'descripcion': 'Notificación para cursos que están por finalizar',
                'prioridad': 'ALTA',
                'color': 'info',
                'icono': 'fa-calendar-check'
            },
            {
                'nombre': 'Ausencias Consecutivas',
                'codigo': 'AUSENCIAS_CONSECUTIVAS',
                'descripcion': 'Alumno con 2 o más ausencias consecutivas',
                'prioridad': 'URGENTE',
                'color': 'danger',
                'icono': 'fa-user-times'
            },
            {
                'nombre': 'Pagos Atrasados',
                'codigo': 'PAGOS_ATRASADOS',
                'descripcion': 'Pagos con fecha de vencimiento atrasada',
                'prioridad': 'ALTA',
                'color': 'danger',
                'icono': 'fa-money-bill-wave'
            },
            {
                'nombre': 'Alumnos Pendientes',
                'codigo': 'ALUMNOS_PENDIENTES',
                'descripcion': 'Alumnos con tareas pendientes de seguimiento',
                'prioridad': 'MEDIA',
                'color': 'warning',
                'icono': 'fa-users'
            },
            {
                'nombre': 'Certificados Pendientes',
                'codigo': 'CERTIFICADOS_PENDIENTES',
                'descripcion': 'Cursos que requieren preparación de certificados',
                'prioridad': 'MEDIA',
                'color': 'info',
                'icono': 'fa-file-certificate'
            }
        ]
        
        for tipo_data in tipos:
            TipoNotificacion.objects.get_or_create(
                codigo=tipo_data['codigo'],
                defaults=tipo_data
            )
    
    @staticmethod
    def generar_notificaciones_automaticas():
        """Generar todas las notificaciones automáticas"""
        ServicioNotificaciones.generar_notificaciones_cursos_por_iniciar()
        ServicioNotificaciones.generar_notificaciones_cursos_por_finalizar()
        ServicioNotificaciones.generar_notificaciones_ausencias_consecutivas()
        ServicioNotificaciones.generar_notificaciones_pagos_atrasados()
        ServicioNotificaciones.generar_notificaciones_certificados()
    
    @staticmethod
    def generar_notificaciones_cursos_por_iniciar():
        """Notificar cursos que inician en 10 días"""
        fecha_limite = timezone.now().date() + timedelta(days=10)
        cursos = Curso.objects.filter(
            fecha_inicio=fecha_limite,
            eliminado=False,
            activo=True
        )
        
        try:
            tipo_notif = TipoNotificacion.objects.get(codigo='CURSO_POR_INICIAR')
        except TipoNotificacion.DoesNotExist:
            print("❌ Tipo de notificación CURSO_POR_INICIAR no existe")
            return
        
        # Usuario del sistema para notificaciones automáticas
        usuario_sistema = User.objects.filter(is_superuser=True).first()
        
        usuarios_coordinadores = User.objects.filter(
            Q(groups__name='Administración') | 
            Q(personal__tipo='COORDINADOR') |
            Q(is_superuser=True)
        ).distinct()
        
        for curso in cursos:
            for usuario in usuarios_coordinadores:
                Notificacion.objects.get_or_create(
                    tipo=tipo_notif,
                    curso=curso,
                    usuario_destino=usuario,
                    usuario_origen=usuario_sistema,  # ✅ AGREGADO: Usuario origen para notificaciones automáticas
                    titulo=f"Curso por iniciar: {curso.nombre}",
                    mensaje=f"El curso '{curso.nombre}' inicia el {curso.fecha_inicio}. Recuerde armar los grupos.",
                    prioridad='ALTA',
                    fecha_vencimiento=curso.fecha_inicio,
                    es_manual=False  # ✅ AGREGADO: Indicar que es automática
                )
    
    @staticmethod
    def generar_notificaciones_cursos_por_finalizar():
        """Notificar cursos que finalizan en 15 días"""
        fecha_limite = timezone.now().date() + timedelta(days=15)
        cursos = Curso.objects.filter(
            fecha_fin=fecha_limite,
            eliminado=False,
            activo=True
        )
        
        try:
            tipo_notif = TipoNotificacion.objects.get(codigo='CURSO_POR_FINALIZAR')
        except TipoNotificacion.DoesNotExist:
            print("❌ Tipo de notificación CURSO_POR_FINALIZAR no existe")
            return
        
        # Usuario del sistema para notificaciones automáticas
        usuario_sistema = User.objects.filter(is_superuser=True).first()
        
        usuarios_coordinadores = User.objects.filter(
            Q(groups__name='Administración') | 
            Q(personal__tipo='COORDINADOR') |
            Q(is_superuser=True)
        ).distinct()
        
        for curso in cursos:
            for usuario in usuarios_coordinadores:
                Notificacion.objects.get_or_create(
                    tipo=tipo_notif,
                    curso=curso,
                    usuario_destino=usuario,
                    usuario_origen=usuario_sistema,  # ✅ AGREGADO
                    titulo=f"Curso por finalizar: {curso.nombre}",
                    mensaje=f"El curso '{curso.nombre}' finaliza el {curso.fecha_fin}. Prepare los certificados.",
                    prioridad='ALTA',
                    fecha_vencimiento=curso.fecha_fin,
                    es_manual=False  # ✅ AGREGADO
                )
    
    @staticmethod
    def generar_notificaciones_ausencias_consecutivas():
        """Notificar alumnos con 2+ ausencias consecutivas"""
        # Obtener todas las inscripciones activas
        inscripciones_activas = Inscripcion.objects.filter(
            activo=True,
            estado__in=['INSCRIPTO', 'CURSANDO']
        )
        
        try:
            tipo_notif = TipoNotificacion.objects.get(codigo='AUSENCIAS_CONSECUTIVAS')
        except TipoNotificacion.DoesNotExist:
            print("❌ Tipo de notificación AUSENCIAS_CONSECUTIVAS no existe")
            return
            
        # Usuario del sistema para notificaciones automáticas
        usuario_sistema = User.objects.filter(is_superuser=True).first()
        
        hoy = timezone.now().date()
        
        for inscripcion in inscripciones_activas:
            # Obtener asistencias de los últimos 5 días
            fecha_inicio = hoy - timedelta(days=5)
            asistencias = Asistencia.objects.filter(
                inscripcion=inscripcion,
                fecha__gte=fecha_inicio,
                fecha__lte=hoy
            ).order_by('-fecha')
            
            # Verificar 2 ausencias consecutivas
            ausencias_consecutivas = 0
            for asistencia in asistencias:
                if not asistencia.presente:
                    ausencias_consecutivas += 1
                    if ausencias_consecutivas >= 2:
                        # Crear notificación
                        usuarios = User.objects.filter(
                            Q(personal__tipo='COORDINADOR') |
                            Q(personal=inscripcion.curso.profesor) |
                            Q(is_superuser=True)
                        ).distinct()
                        
                        for usuario in usuarios:
                            Notificacion.objects.get_or_create(
                                tipo=tipo_notif,
                                alumno=inscripcion.alumno,
                                curso=inscripcion.curso,
                                usuario_destino=usuario,
                                usuario_origen=usuario_sistema,  # ✅ AGREGADO
                                titulo=f"Ausencias consecutivas: {inscripcion.alumno.nombre_completo}",
                                mensaje=f"El alumno {inscripcion.alumno.nombre_completo} tiene {ausencias_consecutivas} ausencias consecutivas en {inscripcion.curso.nombre}.",
                                prioridad='URGENTE',
                                es_manual=False  # ✅ AGREGADO
                            )
                        break
                else:
                    ausencias_consecutivas = 0
    
    @staticmethod
    def generar_notificaciones_pagos_atrasados():
        """Notificar pagos atrasados según periodos"""
        # TODO: Implementar lógica específica para pagos atrasados
        # Basado en los periodos 1-10 y 11-20 días
        print("⚠️  Función generar_notificaciones_pagos_atrasados pendiente de implementar")
        pass
    
    @staticmethod
    def generar_notificaciones_certificados():
        """Notificar certificados pendientes para cursos finalizados"""
        cursos_finalizados = Curso.objects.filter(
            fecha_fin__lte=timezone.now().date(),
            eliminado=False,
            activo=True
        )
        
        try:
            tipo_notif = TipoNotificacion.objects.get(codigo='CERTIFICADOS_PENDIENTES')
        except TipoNotificacion.DoesNotExist:
            print("❌ Tipo de notificación CERTIFICADOS_PENDIENTES no existe")
            return
        
        # Usuario del sistema para notificaciones automáticas
        usuario_sistema = User.objects.filter(is_superuser=True).first()
        
        usuarios_coordinadores = User.objects.filter(
            Q(groups__name='Administración') | 
            Q(personal__tipo='COORDINADOR') |
            Q(is_superuser=True)
        ).distinct()
        
        for curso in cursos_finalizados:
            # Contar alumnos aprobados sin certificado
            alumnos_aprobados = Inscripcion.objects.filter(
                curso=curso,
                estado='APROBADO'
            ).count()
            
            if alumnos_aprobados > 0:
                for usuario in usuarios_coordinadores:
                    Notificacion.objects.get_or_create(
                        tipo=tipo_notif,
                        curso=curso,
                        usuario_destino=usuario,
                        usuario_origen=usuario_sistema,  # ✅ AGREGADO
                        titulo=f"Certificados pendientes: {curso.nombre}",
                        mensaje=f"El curso '{curso.nombre}' tiene {alumnos_aprobados} alumnos aprobados que requieren certificados.",
                        prioridad='MEDIA',
                        es_manual=False  # ✅ AGREGADO
                    )
    
    @staticmethod
    def limpiar_notificaciones_antiguas(dias=30):
        """Archivar notificaciones más antiguas que X días"""
        fecha_limite = timezone.now() - timedelta(days=dias)
        
        notificaciones_antiguas = Notificacion.objects.filter(
            fecha_creacion__lt=fecha_limite,
            estado__in=['LEIDA', 'REALIZADA']
        )
        
        count = notificaciones_antiguas.update(activo=False)
        print(f"📁 Archivadas {count} notificaciones antiguas")
        
        return count