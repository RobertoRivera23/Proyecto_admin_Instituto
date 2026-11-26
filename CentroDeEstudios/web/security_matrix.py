"""
Matriz de seguridad que define qué roles pueden realizar qué acciones
con qué permisos específicos
"""

MATRIZ_SEGURIDAD = {
    'LECTURA': {
        'roles': ['LIMPEZA', 'SEGURIDAD', 'OTRO'],
        'permisos': [
            'web.can_view_staff',
            'web.can_view_courses',
            'web.can_view_students',
        ],
        'descripcion': 'Solo visualización básica'
    },
    
    'SECRETARIA': {
        'roles': ['SECRETARIA'],
        'permisos': [
            'web.can_view_staff',
            'web.can_view_courses', 
            'web.can_view_students',
            'web.can_edit_staff',
            'web.can_manage_students',
            'auth.can_view_users',
        ],
        'descripcion': 'Gestión operativa diaria'
    },
    
    'COORDINADOR': {
        'roles': ['COORDINADOR'],
        'permisos': [
            'web.can_view_staff',
            'web.can_edit_staff',
            'web.can_manage_courses',
            'web.can_manage_students',
            'auth.can_view_users',
            'auth.can_edit_users',
            'web.can_view_reports',
            'web.can_generate_reports',
        ],
        'descripcion': 'Gestión académica y reportes'
    },
    
    'ADMINISTRADOR': {
        'roles': ['ADMINISTRATIVO'],
        'permisos': [
            'web.can_manage_staff',
            'web.can_manage_courses',
            'web.can_manage_students',
            'auth.can_view_users',
            'auth.can_edit_users',
            'auth.can_manage_user_accounts',
            'web.can_view_reports',
            'web.can_generate_reports',
            'web.can_view_audit_logs',
        ],
        'descripcion': 'Gestión completa del sistema'
    },
    
    'SUPERVISOR_SEGURIDAD': {
        'roles': ['ADMINISTRATIVO'],  # Mismo rol pero con permisos extra
        'permisos': [
            'web.can_manage_staff',
            'web.can_manage_courses',
            'web.can_manage_students',
            'auth.can_view_users',
            'auth.can_edit_users',
            'auth.can_manage_user_accounts',
            'auth.can_manage_permissions',
            'web.can_view_reports',
            'web.can_generate_reports',
            'web.can_view_audit_logs',
            'web.can_view_security_logs',
            'web.can_manage_system',
        ],
        'descripcion': 'Acceso completo incluyendo auditoría'
    }
}

def verificar_acceso_seguro(usuario, accion, recurso=None):
    """
    Verifica si un usuario puede realizar una acción específica
    según su rol Y permisos
    """
    try:
        personal = usuario.personal
        rol = personal.tipo
        
        # Buscar configuración del rol
        config_rol = None
        for nivel, config in MATRIZ_SEGURIDAD.items():
            if rol in config['roles']:
                config_rol = config
                break
        
        if not config_rol:
            return False, "Rol no tiene configuración de seguridad"
        
        # Verificar permisos requeridos para la acción
        permisos_requeridos = obtener_permisos_para_accion(accion, recurso)
        
        for permiso in permisos_requeridos:
            if not usuario.has_perm(permiso):
                return False, f"Falta permiso: {permiso}"
        
        return True, "Acceso permitido"
        
    except Personal.DoesNotExist:
        return False, "Usuario sin perfil de personal"

def obtener_permisos_para_accion(accion, recurso=None):
    """
    Define qué permisos se necesitan para cada acción
    """
    matriz_permisos = {
        'ver_personal': ['web.can_view_staff'],
        'crear_personal': ['web.can_add_staff'],
        'editar_personal': ['web.can_edit_staff'],
        'eliminar_personal': ['web.can_delete_staff'],
        'gestionar_usuarios': ['auth.can_manage_user_accounts'],
        'asignar_permisos': ['auth.can_manage_permissions'],
        'ver_auditoria': ['web.can_view_audit_logs'],
        'ver_logs_seguridad': ['web.can_view_security_logs'],
    }
    
    return matriz_permisos.get(accion, [])