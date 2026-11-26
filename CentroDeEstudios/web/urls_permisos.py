# # web/urls_permisos.py
# from django.urls import path
# from .views_profesores import *

# app_name = 'permisos'

# urlpatterns = [
#     # Dashboard
#     path('dashboard/', gestion_permisos_dashboard, name='dashboard_permisos'),
    
#     # Grupos
#     path('grupos/', listar_grupos_permisos, name='listar_grupos_permisos'),
#     path('grupos/editar/<int:grupo_id>/', editar_permisos_grupo, name='editar_permisos_grupo'),
#     path('grupos/crear/', crear_nuevo_grupo, name='crear_nuevo_grupo'),
#     path('grupos/eliminar/<int:grupo_id>/', eliminar_grupo, name='eliminar_grupo'),
    
#     # Permisos
#     path('permisos/crear/', crear_nuevo_permiso, name='crear_nuevo_permiso'),
    
#     # Usuarios
#     path('usuarios/asignar/', asignar_permisos_usuario, name='asignar_permisos_usuario'),
#     path('usuarios/<int:user_id>/', ver_usuario_permisos, name='ver_usuario_permisos'),
# ]