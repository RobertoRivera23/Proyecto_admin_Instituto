from django import template
print("🔵 Cargando custom_filters")
register = template.Library()

@register.filter
def filter_porcentaje(queryset, rango):
    """Filtra por rango de porcentaje (ej: '80,100')"""
    try:
        min_val, max_val = map(int, rango.split(','))
        return [item for item in queryset if min_val <= item['porcentaje_asistencia'] <= max_val]
    except:
        return []

@register.filter
def filter_porcentaje_max(queryset, max_val):
    """Filtra por porcentaje máximo"""
    try:
        return [item for item in queryset if item['porcentaje_asistencia'] <= int(max_val)]
    except:
        return []

@register.filter
def get_attr(obj, attr_name):
    """Obtiene un atributo de un objeto dinámicamente"""
    if hasattr(obj, attr_name):
        return getattr(obj, attr_name)
    elif isinstance(obj, dict) and attr_name in obj:
        return obj[attr_name]
    return None

@register.filter
def nombre_completo(user):
    """Devuelve el nombre completo del usuario"""
    if hasattr(user, 'get_full_name'):
        full_name = user.get_full_name()
        if full_name:
            return full_name
    return user.username

@register.filter
def order_by_alumno(alumnos_stats_dict):
    """
    Recibe el diccionario alumnos_stats (con inscripcion_id como clave)
    y retorna una lista de tuplas (inscripcion_id, stats) ordenadas
    por apellido y nombre del alumno.
    """
    items = list(alumnos_stats_dict.items())
    items.sort(key=lambda x: (x[1]['alumno'].apellido, x[1]['alumno'].nombre))
    return items

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def test_filter(value):
    return "Funciona"

@register.filter
def debug_type(value):
    return str(type(value))

@register.filter
def dict_key(d, key):
    return d.get(key)