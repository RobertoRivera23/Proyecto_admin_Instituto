from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.contrib.staticfiles.urls import static
from django.conf.urls.static import static
from . import views
from . import views_profesores

urlpatterns = [         

    path('', views.index, name='index'), 
    
    path('buscar/', views.buscar_global, name='buscar_global'),
            
    path('alumnos/alta_alumno/', views.alta_alumno, name='alta_alumno'),
    path('profesores/alta_profesor/', views.alta_profesor, name='alta_profesor'),
  
    path('alta_inscripcion/<int:id>', views.alta_inscripcion, name='alta_inscripcion'),
    path('alumnos/edit_alumno/<int:id>/', views.edit_alumno, name='edit_alumno'),
    path('alumnos/listar_alumno/', views.listar_alumno, name='listar_alumno'),
    path('profesores/listar_profesores/', views.listar_profesores, name='listar_profesores'),
    
    path('alumnos/mostrar_alumno/<int:id>/', views.mostrar_alumno, name='mostrar_alumno'),
    path('profesores/mostrar_profesor/<int:id>/', views.mostrar_profesor, name='mostrar_profesor'),
    
    path('alumnos/eliminar/<int:id>/', views.eliminar_alumno, name='eliminar_alumno'),
    
    path('alumnos/eliminados/', views.alumnos_eliminados, name='alumnos_eliminados'),
    path('alumnos/restaurar/<int:id>/', views.restaurar_alumno, name='restaurar_alumno'),
    path('alumnos/<int:alumno_id>/historial-completo/', views.historial_completo_alumno, name='historial_completo_alumno'),
    path('alumnos/modal/<int:alumno_id>/', views.modal_detalle_alumno, name='modal_detalle_alumno'),
    path('alumno/<int:id>/archivo/eliminar/<int:archivo_id>/', views.eliminar_archivo_alumno, name='eliminar_archivo_alumno'),
    path('alumno/confirmar-eliminar/<int:id>/', views.confirmar_eliminar_alumno, name='confirmar_eliminar_alumno'),


    path('cursos/', views.listar_cursos, name='listar_cursos'),
    path('cursos/alta_curso/', views.alta_curso, name='alta_curso'),
    path('cursos/<int:curso_id>/alumnos/', views.listar_alumnos_curso_universal, name='listar_alumnos_curso'),  # ← ÚNICA URL
    #path('cursos/<int:curso_id>/asistencia/', views.tomar_asistencia_secretaria, name='tomar_asistencia_secretaria'),
    path('cursos/<int:curso_id>/editar/', views.editar_curso, name='editar_curso'),
    path('cursos/<int:curso_id>/eliminar/', views.eliminar_curso, name='eliminar_curso'),
    path('cursos/eliminados/', views.cursos_eliminados, name='cursos_eliminados'),
    path('cursos-eliminados/<int:curso_id>/restaurar/', views.restaurar_curso, name='restaurar_curso'),
    #path('cursos/<int:curso_id>/asistencia-completa/', views.tomar_asistencia_completa, name='tomar_asistencia_completa'),
    path('cursos/mostrar/<int:curso_id>/', views.mostrar_curso, name='mostrar_curso'),
    path('cursos/archivo/eliminar/<int:curso_id>/<int:archivo_id>/', views.eliminar_archivo_curso, name='eliminar_archivo_curso'),

    # web/urls.py - SIMPLIFICA las URLs


    path('curso/<int:curso_id>/asistencia/', views_profesores.tomar_asistencia_unificada, name='tomar_asistencia_unificada'),
    
    # Ruta para profesores (alias para compatibilidad)
    path('profesor/curso/<int:curso_id>/asistencia/', 
         views_profesores.tomar_asistencia_unificada, 
         name='tomar_asistencia_profesor'),
    
    
    path('debug/cursos-eliminados/', views.debug_cursos_eliminados, name='debug_cursos_eliminados'),
    
    
    path('obtener_fechas_curso/<int:curso_id>/', views.obtener_fechas_curso, name='obtener_fechas_curso'),
    
    path('debug/cursos/', views.debug_todos_cursos, name='debug_cursos'),
    
    path('personal/', views.lista_personal, name='listar_personal'),
    path('personal/crear/', views.crear_personal, name='crear_personal'),
    path('personal/<int:personal_id>/', views.detalle_personal, name='detalle_personal'),
    path('personal/<int:personal_id>/editar/', views.editar_personal, name='editar_personal'),
    path('personal/<int:personal_id>/eliminar/', views.eliminar_personal, name='eliminar_personal'),
    path('personal/<int:personal_id>/toggle-activo/', views.toggle_activo_personal, name='toggle_activo_personal'),
    path('personal/<int:personal_id>/cambiar-password/', views.cambiar_password_usuario_por_personal, name='cambiar_password_usuario_por_personal'),

    path('backups/', views.listar_backups_view, name='listar_backups'),
    path('backups/restaurar/<int:backup_id>/', views.restaurar_backup_view, name='restaurar_backup'),
    path('backups/eliminar/<int:backup_id>/', views.eliminar_backup_view, name='eliminar_backup'),

    path('profesores/', views.listar_profesores, name='listar_profesores'),
    path('profesores/alta/', views.alta_profesor, name='alta_profesor'),
    path('profesores/eliminados/', views.profesores_eliminados, name='profesores_eliminados'),
    path('profesores/<int:id>/', views.mostrar_profesor, name='mostrar_profesor'),
    path('profesores/<int:id>/editar/', views.editar_profesor, name='editar_profesor'),
    path('profesores/<int:id>/eliminar/', views.eliminar_profesor, name='eliminar_profesor'),
    path('profesores/<int:id>/restaurar/', views.restaurar_profesor, name='restaurar_profesor'),
    
    path('profesor/cursos/', views.cursos_profesor, name='cursos_profesor'),
    path('profesor/curso/<int:curso_id>/gestion/', views.gestionar_curso, name='gestionar_curso'),
    #path('profesor/curso/<int:curso_id>/asistencias/', views_profesores.reporte_asistencia_curso, name='reporte_asistencia_curso'),
    path('curso/<int:curso_id>/asistencia/reporte/', views.reporte_asistencias, name='reporte_asistencia_curso'),
    path('curso/<int:curso_id>/asistencia/exportar-excel/', 
         views_profesores.exportar_asistencia, 
         name='exportar_asistencia'),
    
    path('curso/<int:curso_id>/asistencia/exportar-csv/', 
         views_profesores.exportar_asistencia_csv, 
         name='exportar_asistencia_csv'),
    
    
    path('profesor/switch-modo/', views_profesores.switch_modo_profesor, name='switch_modo_profesor'),
    # Dashboard y perfil
    path('profesor/dashboard/', views_profesores.dashboard_profesor, name='dashboard_profesor'),
    path('profesor/perfil/', views_profesores.perfil_profesor, name='perfil_profesor'),
    
    # Cursos
    path('profesor/mis-cursos/', views_profesores.mis_cursos, name='mis_cursos_profesor'),
    path('profesor/curso/<int:curso_id>/', views_profesores.detalle_curso_profesor, name='detalle_curso_profesor'),
    path('dashboard/profesor/<int:profesor_id>/', views_profesores.dashboard_profesor, name='dashboard_profesor_detalle'),
    
    # Asistencia path('profesor/curso/<int:curso_id>/asistencia/', views_profesores.tomar_asistencia_profesor, name='tomar_asistencia_profesor'),
    
    
    # Notas y exámenes
    path('profesor/curso/<int:curso_id>/notas/', views_profesores.gestionar_notas, name='gestionar_notas'),
    path('profesor/inscripcion/<int:inscripcion_id>/examen/', views_profesores.agregar_examen_individual, name='agregar_examen_individual'),
    # web/urls.py - AGREGAR ESTAS URLs NUEVAS

    # Vistas de profesor con parámetros opcionales para admin
    path('profesor/perfil/<int:profesor_id>/', views_profesores.perfil_profesor_detalle, name='perfil_profesor_detalle'),
    path('profesor/mis-cursos/<int:profesor_id>/', views_profesores.mis_cursos_detalle, name='mis_cursos_profesor_detalle'),
    path('profesor/dashboard/admin/', views_profesores.dashboard_admin_general, name='dashboard_admin_general'),

    # Dashboard con parámetro
    path('profesor/dashboard/<int:profesor_id>/', views_profesores.dashboard_profesor_detalle, name='dashboard_profesor_detalle'),
    
    
     #  path('examen/agregar/<int:inscripcion_id>/', views_profesores.agregar_examen_individual, name='agregar_examen'),
    path('examen/editar/<int:examen_id>/', views_profesores.editar_examen, name='editar_examen'),
    path('examen/eliminar/<int:examen_id>/', views_profesores.eliminar_examen, name='eliminar_examen'),
    
    # Observaciones
    path('profesor/curso/<int:curso_id>/observaciones/', views.listar_observaciones_curso, name='listar_observaciones_curso'),
    path('profesor/curso/<int:curso_id>/alumno/<int:alumno_id>/observacion/', views.agregar_observacion_alumno, name='agregar_observacion_alumno'),
    path('profesor/curso/<int:curso_id>/alumno/<int:alumno_id>/', views.detalle_alumno_profesor, name='detalle_alumno_profesor'),
    
    
    
    # AJAX/Rápidas
    path('profesor/observacion/<int:observacion_id>/resolver/', views.marcar_observacion_resuelta, name='marcar_observacion_resuelta'),
    path('profesor/curso/<int:curso_id>/estadisticas/', views_profesores.obtener_estadisticas_curso, name='obtener_estadisticas_curso'),

    path('pagos/pago_alta/', views.pago_create, name='pago_alta'),
    path('get_precio_curso/', views.get_precio_curso, name='get_precio_curso'),


   
    path('inscripciones/', views.listar_inscripciones, name='listar_inscripciones'),
    path('inscripciones/alumno/<int:alumno_id>/', views.inscripciones_alumno, name='inscripciones_alumno'),
    path('inscripciones/nueva/', views.nueva_inscripcion, name='nueva_inscripcion'),
    path('inscripciones/nueva/<int:alumno_id>/', views.nueva_inscripcion, name='nueva_inscripcion_con_alumno'),
    path('inscripciones/editar/<int:inscripcion_id>/', views.editar_inscripcion, name='editar_inscripcion'),
    path('inscripciones/cambiar-estado/<int:inscripcion_id>/', views.cambiar_estado_inscripcion, name='cambiar_estado_inscripcion'),
    path('inscripciones/eliminar/<int:inscripcion_id>/', views.eliminar_inscripcion, name='eliminar_inscripcion'),
    path('inscripciones/eliminadas/', views.inscripciones_eliminadas, name='inscripciones_eliminadas'),
    path('inscripciones/restaurar/<int:inscripcion_id>/', views.restaurar_inscripcion, name='restaurar_inscripcion'),
    path('inscripciones/certificado/<int:inscripcion_id>/', views.generar_certificado_pdf, name='generar_certificado_pdf'),
    path('inscripciones/buscar-alumnos/', views.buscar_alumnos_ajax, name='buscar_alumnos_ajax'),
    path('inscripciones/detalle/<int:inscripcion_id>/', views.detalle_inscripcion, name='detalle_inscripcion'),
    
   

    path('inscripciones/<int:inscripcion_id>/generar-certificado/', views.generar_certificado_pdf, name='generar_certificado_pdf'),
    path('certificados/<str:codigo>/', views.ver_certificado, name='ver_certificado'),
    path('certificados/<str:codigo>/descargar/', views.descargar_certificado, name='descargar_certificado'),
    path('verificar-certificado/', views.verificar_certificado, name='verificar_certificado'),
    
    # URLs de Gestión de Usuarios - MANTÉN SOLO UNA VEZ
    path('usuarios/gestion/', views.gestion_usuarios, name='gestion_usuarios'),
    path('usuarios/<int:personal_id>/permisos/', views.asignar_permisos, name='asignar_permisos'),
    
    path('usuarios/<int:personal_id>/toggle-activo/', views.toggle_activo_usuario, name='toggle_activo_usuario'),
    path('usuarios/<int:personal_id>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),
    path('usuarios/dashboard', views.dashboard_personalizado, name='dashboard'),
    path('usuarios/editar/<int:user_id>/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/cambiar-contraseña/<int:user_id>/', views.cambiar_password_usuario, name='cambiar_password_usuario'),
    
    # Dashboards
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('dashboard/alumno/', views.dashboard_alumno, name='dashboard_alumno'),
    path('dashboard/profesor/', views.dashboard_profesor, name='dashboard_profesor'),
    path('dashboard/administracion/', views.dashboard_administracion, name='dashboard_administracion'),
    path('dashboard/personal/', views.dashboard_personal, name='dashboard_personal'),
    
    
    path('permisos/dashboard/', views.dashboard_permisos, name='dashboard_permisos'),
    path('permisos/grupos/', views.listar_grupos_permisos, name='listar_grupos_permisos'),
    path('permisos/grupos/crear/', views.crear_nuevo_grupo, name='crear_nuevo_grupo'),
    path('permisos/permisos/crear/', views.crear_nuevo_permiso, name='crear_nuevo_permiso'),
    path('permisos/asignar/<int:user_id>/', views.asignar_permisos_usuario, name='asignar_permisos_usuario'),
    path('permisos/asignar/', views.asignar_permisos_usuario, name='asignar_permisos_usuario'),  # Sin ID para seleccionar
    path('permisos/grupos/editar/<int:grupo_id>/', views.editar_permisos_grupo, name='editar_permisos_grupo'),
    path('permisos/grupos/eliminar/<int:grupo_id>/', views.eliminar_grupo, name='eliminar_grupo'),
    path('permisos/asignar/', views.asignar_permisos_usuario, name='asignar_permisos_usuario'),
    path('permisos/asignar/<int:user_id>/', views.asignar_permisos_usuario, name='asignar_permisos_usuario'),
    
    # Gestión de usuarios
    path('usuarios/gestion/', views.gestion_usuarios, name='gestion_usuarios'),
    path('usuarios/<int:persona_id>/asignar/', views.asignar_usuario_persona, name='asignar_usuario_persona'),
    path('usuarios/<int:user_id>/desactivar/', views.desactivar_usuario, name='desactivar_usuario'),
    path('usuarios/<int:user_id>/reactivar/', views.reactivar_usuario, name='reactivar_usuario'),
    path('usuarios/<int:user_id>/reset-password/', views.reset_password_usuario, name='reset_password_usuario'),
    
        # URL para página de permisos denegados
    path('sin-permisos/', views.sin_permiso_personal, name='sin_permiso_personal'),
    
    # También para usuarios sin personal (puede ser la misma)
    path('sin-personal/', views.sin_permiso_personal, name='sin_personal'),
    
    
    # Perfil de usuario
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
    #path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    #path('perfil/cambiar-password/', views.CambiarPasswordView.as_view(), name='cambiar_password'),
    
    # Perfil - MANTÉN SOLO UNA VEZ
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
    
    path('perfil/administrativo/', views.perfil_administrativo, name='perfil_administrativo'),

    path('registro/', views.RegistroView.as_view(), name='registro'),
    path('login/', auth_views.LoginView.as_view(template_name='usuarios/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    
    path('resetear_contrasena/', 
        views.CustomPasswordResetView.as_view(
            template_name='usuarios/resetear_contrasena.html',
            email_template_name='usuarios/password_reset_email.html',
            html_email_template_name='usuarios/password_reset_email.html',
            subject_template_name='usuarios/password_reset_subject.txt'
        ),
        name='resetear_contrasena'),
    #Asociar personal
    path('usuarios/asociar/<int:user_id>/personal/<int:personal_id>/', 
     views.asociar_usuario_personal, 
     name='asociar_usuario_personal'),
    

   # Cambio de contraseña (logueado) - USA TU TEMPLATE PERSONALIZADO
path('cambiar_contrasena/',
     auth_views.PasswordChangeView.as_view(
         template_name='usuarios/cambiar_contrasena.html',  # ← CAMBIA ESTA LÍNEA
         success_url='/'
     ),
    name='cambiar_contrasena'),

# Recuperación de contraseña (no logueado) - USA TUS TEMPLATES PERSONALIZADOS
path('resetear_contrasena/',
    auth_views.PasswordResetView.as_view(
        template_name='usuarios/resetear_contrasena.html',
        email_template_name='usuarios/password_reset_email.html',  # Usa HTML como texto plano también
        html_email_template_name='usuarios/password_reset_email.html',  # Y como HTML
        subject_template_name='usuarios/password_reset_subject.txt'  
     ),
    name='resetear_contrasena'),
 
path('resetear_contrasena/done/', 
     auth_views.PasswordResetDoneView.as_view(
         template_name='usuarios/resetear_contrasena_done.html' 
     ), 
     name='password_reset_done'),
 
path('resetear_contrasena/confirmar/<uidb64>/<token>/', 
     auth_views.PasswordResetConfirmView.as_view(
         template_name='usuarios/resetear_contrasena_confirm.html'  
     ), 
     name='password_reset_confirm'),
 
path('resetear_contrasena/completo/', 
     auth_views.PasswordResetCompleteView.as_view(
         template_name='usuarios/resetear_contrasena_completo.html'  # ← CREA ESTE TEMPLATE
     ), 
     name='password_reset_complete'),

    # Auditoría y seguridad
    path('auditoria/logs/', views.ver_logs_auditoria, name='logs_auditoria'),
    path('auditoria/seguridad/', views.ver_logs_seguridad, name='logs_seguridad'),
    
    
    # Notificaciones
    path('notificaciones/dropdown/', views.notificaciones_dropdown, name='notificaciones_dropdown'),
    path('notificaciones/marcar_leida/<int:id>/', views.marcar_leida, name='marcar_leida'),
    path('notificaciones/marcar_realizada/<int:id>/', views.marcar_realizada, name='marcar_realizada'),
    path('notificaciones/cambiar_estado/<int:id>/', views.cambiar_estado_notificacion, name='cambiar_estado_notificacion'),
    path('notificaciones/', views.listar_notificaciones, name='listar_notificaciones'),
    path('notificaciones/dashboard/', views.dashboard_coordinador, name='dashboard_notificaciones'),
    path('notificaciones/crear-rapida/', views.crear_notificacion_rapida, name='crear_notificacion_rapida'),
    path('notificaciones/asignar-tarea/', views.asignar_tarea_companero, name='asignar_tarea_companero'),
    path('notificaciones/papelera/', views.papelera_notificaciones, name='papelera_notificaciones'),
    path('notificaciones/<int:notificacion_id>/eliminar/', views.eliminar_notificacion, name='eliminar_notificacion'),
    path('notificaciones/<int:notificacion_id>/restaurar/', views.restaurar_notificacion, name='restaurar_notificacion'),
    path('notificaciones/<int:notificacion_id>/eliminar-permanentemente/', views.eliminar_permanentemente_notificacion, name='eliminar_permanentemente_notificacion'),
    path('notificaciones/vaciar-papelera/', views.vaciar_papelera, name='vaciar_papelera'),
    
    path('notificaciones/generar-mora/', views.generar_notificaciones_mora_manual, name='generar_notificaciones_mora_manual'),
    path('notificaciones/recordatorios-pago/', views.generar_recordatorios_pago, name='generar_recordatorios_pago'),
    path('notificaciones/exportar-excel/', views.exportar_moras_excel, name='exportar_moras_excel'),
    path('notificaciones/reporte-pdf/', views.reporte_moras_pdf, name='reporte_moras_pdf'),

    
    path('debug/notificaciones/', views.debug_notificaciones, name='debug_notificaciones'),
    path('facturacion/seguimiento-moras/', views.seguimiento_moras, name='seguimiento_moras'),
    path('facturacion/reportes/moras/', views.reporte_moras_pdf, name='reporte_moras_pdf'),
    path('notificaciones/dashboard/', views.dashboard_notificaciones, name='dashboard_notificaciones'),
    
    path('debug/notificaciones-tareas/', views.debug_notificaciones_tareas, name='debug_notificaciones_tareas'),
    path('debug/tareas-rapidas/', views.debug_tareas_rapidas, name='debug_tareas_rapidas'),
    
    #path('gestion-permisos/', include('web.urls_permisos')),
    
    
    
    
    path('debug/permisos/', views_profesores.test_permisos, name='test_permisos'),
        
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)