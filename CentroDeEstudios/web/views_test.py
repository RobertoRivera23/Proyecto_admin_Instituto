from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from .decorators import solo_coordinador_estricto
from .models import Personal

@login_required
@solo_coordinador_estricto
def gestion_permisos_dashboard(request):
    """Dashboard principal de gestión de permisos"""
    # Estadísticas del sistema
    grupos = Group.objects.all().order_by('name')
    permisos_personalizados = Permission.objects.filter(codename__startswith='can_')
    usuarios_coordinadores = User.objects.filter(groups__name='Coordinador')
    
    context = {
        'total_grupos': grupos.count(),
        'total_permisos_personalizados': permisos_personalizados.count(),
        'total_usuarios': User.objects.count(),
        'total_coordinadores': usuarios_coordinadores.count(),
        'grupos_destacados': grupos[:5],  # Primeros 5 grupos
    }
    
    return render(request, 'permisos/dashboard.html', context)

@login_required
@solo_coordinador_estricto
def listar_grupos_permisos(request):
    """Lista todos los grupos y sus permisos"""
    grupos = Group.objects.all().order_by('name')
    
    # Obtener permisos agrupados por tipo
    permisos_web = Permission.objects.filter(
        codename__startswith='can_',
        content_type__app_label='web'
    ).order_by('codename')
    
    permisos_auth = Permission.objects.filter(
        codename__startswith='can_',
        content_type__app_label='auth'
    ).order_by('codename')
    
    context = {
        'grupos': grupos,
        'permisos_web': permisos_web,
        'permisos_auth': permisos_auth,
        'total_permisos': Permission.objects.filter(codename__startswith='can_').count(),
    }
    
    return render(request, 'permisos/listar_grupos.html', context)

@login_required
@solo_coordinador_estricto
def editar_permisos_grupo(request, grupo_id):
    """Edita los permisos de un grupo específico"""
    try:
        grupo = Group.objects.get(id=grupo_id)
    except Group.DoesNotExist:
        messages.error(request, "Grupo no encontrado")
        return redirect('listar_grupos_permisos')
    
    if request.method == 'POST':
        # Obtener lista de permisos seleccionados
        permisos_seleccionados = request.POST.getlist('permisos')
        
        with transaction.atomic():
            # Limpiar permisos actuales del grupo
            grupo.permissions.clear()
            
            # Asignar nuevos permisos
            for perm_id in permisos_seleccionados:
                try:
                    perm = Permission.objects.get(id=perm_id)
                    grupo.permissions.add(perm)
                except Permission.DoesNotExist:
                    continue
            
            messages.success(request, f"✅ Permisos actualizados para el grupo '{grupo.name}'")
        
        return redirect('permisos:listar_grupos_permisos')
    
    # Obtener todos los permisos personalizados
    permisos_personalizados = Permission.objects.filter(
        codename__startswith='can_'
    ).order_by('content_type__app_label', 'codename')
    
    # Obtener permisos actuales del grupo
    permisos_actuales = grupo.permissions.filter(codename__startswith='can_').values_list('id', flat=True)
    
    context = {
        'grupo': grupo,
        'permisos': permisos_personalizados,
        'permisos_actuales': list(permisos_actuales),
    }
    
    return render(request, 'permisos/editar_grupo.html', context)

@login_required
@solo_coordinador_estricto
def crear_nuevo_permiso(request):
    """Crea un nuevo permiso personalizado"""
    if request.method == 'POST':
        nombre_permiso = request.POST.get('nombre_permiso', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo_permiso = request.POST.get('tipo_permiso', 'web')  # web o auth
        
        if not nombre_permiso:
            messages.error(request, "Debe ingresar un nombre para el permiso")
            return redirect('permisos:crear_nuevo_permiso')
        
        # Validar formato
        if not nombre_permiso.startswith('can_'):
            nombre_permiso = f"can_{nombre_permiso}"
        
        # Verificar si ya existe
        if Permission.objects.filter(codename=nombre_permiso).exists():
            messages.warning(request, f"El permiso '{nombre_permiso}' ya existe")
            return redirect('permisos:crear_nuevo_permiso')
        
        # Determinar content_type
        if tipo_permiso == 'auth':
            ct, _ = ContentType.objects.get_or_create(app_label='auth', model='user')
        else:
            ct, _ = ContentType.objects.get_or_create(app_label='web', model='personal')
        
        # Crear nombre amigable
        nombre_amigable = descripcion if descripcion else nombre_permiso.replace('_', ' ').title()
        
        try:
            perm = Permission.objects.create(
                codename=nombre_permiso,
                name=nombre_amigable,
                content_type=ct
            )
            
            messages.success(request, f"✅ Permiso '{nombre_permiso}' creado exitosamente")
            return redirect('permisos:listar_grupos_permisos')
            
        except Exception as e:
            messages.error(request, f"❌ Error al crear permiso: {str(e)}")
    
    return render(request, 'permisos/crear_permiso.html')

@login_required
@solo_coordinador_estricto
def asignar_permisos_usuario(request):
    """Asigna permisos directamente a un usuario específico"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        permisos_ids = request.POST.getlist('permisos_usuario')
        
        try:
            usuario = User.objects.get(username=username)
            
            with transaction.atomic():
                # Limpiar permisos personalizados actuales
                permisos_actuales = usuario.user_permissions.filter(codename__startswith='can_')
                usuario.user_permissions.remove(*permisos_actuales)
                
                # Asignar nuevos permisos
                for perm_id in permisos_ids:
                    try:
                        perm = Permission.objects.get(id=perm_id)
                        usuario.user_permissions.add(perm)
                    except Permission.DoesNotExist:
                        continue
                
                messages.success(request, f"✅ Permisos asignados al usuario '{username}'")
                
        except User.DoesNotExist:
            messages.error(request, f"❌ Usuario '{username}' no encontrado")
    
    # Obtener usuarios del sistema (excluyendo superusuarios si quieres)
    usuarios = User.objects.filter(is_active=True).order_by('username')
    permisos = Permission.objects.filter(codename__startswith='can_').order_by('codename')
    
    context = {
        'usuarios': usuarios,
        'permisos': permisos,
    }
    
    return render(request, 'permisos/asignar_usuario.html', context)

@login_required
@solo_coordinador_estricto
def ver_usuario_permisos(request, user_id):
    """Muestra los permisos de un usuario específico"""
    try:
        usuario = User.objects.get(id=user_id)
        
        # Obtener personal asociado si existe
        try:
            personal = Personal.objects.get(user=usuario)
            rol = personal.tipo
        except Personal.DoesNotExist:
            personal = None
            rol = "Sin rol asignado"
        
        # Obtener permisos
        permisos_directos = usuario.user_permissions.filter(codename__startswith='can_')
        grupos = usuario.groups.all()
        
        # Permisos por grupos
        permisos_grupos = []
        for grupo in grupos:
            permisos_grupo = grupo.permissions.filter(codename__startswith='can_')
            if permisos_grupo.exists():
                permisos_grupos.append({
                    'grupo': grupo,
                    'permisos': permisos_grupo
                })
        
        # Todos los permisos (directos + grupos)
        todos_permisos = usuario.get_all_permissions()
        permisos_can = [p for p in todos_permisos if 'can_' in p]
        
        context = {
            'usuario': usuario,
            'personal': personal,
            'rol': rol,
            'permisos_directos': permisos_directos,
            'grupos': grupos,
            'permisos_grupos': permisos_grupos,
            'todos_permisos': sorted(permisos_can),
            'total_permisos_can': len(permisos_can),
        }
        
        return render(request, 'permisos/ver_usuario.html', context)
        
    except User.DoesNotExist:
        messages.error(request, "Usuario no encontrado")
        return redirect('permisos:listar_grupos_permisos')

@login_required
@solo_coordinador_estricto
def crear_nuevo_grupo(request):
    """Crea un nuevo grupo con permisos personalizados"""
    if request.method == 'POST':
        nombre_grupo = request.POST.get('nombre_grupo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        permisos_ids = request.POST.getlist('permisos_grupo')
        
        if not nombre_grupo:
            messages.error(request, "Debe ingresar un nombre para el grupo")
            return redirect('permisos:crear_nuevo_grupo')
        
        # Verificar si ya existe
        if Group.objects.filter(name=nombre_grupo).exists():
            messages.warning(request, f"El grupo '{nombre_grupo}' ya existe")
            return redirect('permisos:crear_nuevo_grupo')
        
        try:
            with transaction.atomic():
                # Crear grupo
                grupo = Group.objects.create(name=nombre_grupo)
                
                # Asignar descripción si hay (podrías usar signals para añadir más metadata)
                
                # Asignar permisos
                for perm_id in permisos_ids:
                    try:
                        perm = Permission.objects.get(id=perm_id)
                        grupo.permissions.add(perm)
                    except Permission.DoesNotExist:
                        continue
                
                messages.success(request, f"✅ Grupo '{nombre_grupo}' creado exitosamente")
                return redirect('permisos:listar_grupos_permisos')
                
        except Exception as e:
            messages.error(request, f"❌ Error al crear grupo: {str(e)}")
    
    # Obtener permisos disponibles
    permisos = Permission.objects.filter(codename__startswith='can_').order_by('codename')
    
    context = {
        'permisos': permisos,
    }
    
    return render(request, 'permisos/crear_grupo.html', context)

@login_required
@solo_coordinador_estricto
def eliminar_grupo(request, grupo_id):
    """Elimina un grupo del sistema"""
    try:
        grupo = Group.objects.get(id=grupo_id)
        
        # Prevenir eliminación de grupos críticos
        grupos_criticos = ['Coordinador', 'Administrativo', 'Secretaría', 'Consulta', 'Personal', 'Administración']
        
        if grupo.name in grupos_criticos:
            messages.error(request, f"No se puede eliminar el grupo '{grupo.name}' porque es crítico para el sistema")
            return redirect('permisos:listar_grupos_permisos')
        
        # Verificar si hay usuarios en el grupo
        if grupo.user_set.exists():
            messages.warning(request, f"El grupo '{grupo.name}' tiene usuarios asignados. Transfiéralos primero.")
            return redirect('permisos:listar_grupos_permisos')
        
        nombre_grupo = grupo.name
        grupo.delete()
        
        messages.success(request, f"✅ Grupo '{nombre_grupo}' eliminado exitosamente")
        
    except Group.DoesNotExist:
        messages.error(request, "Grupo no encontrado")
    
    return redirect('permisos:listar_grupos_permisos')