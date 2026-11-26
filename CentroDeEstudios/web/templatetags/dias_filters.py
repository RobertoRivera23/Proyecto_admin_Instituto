from django import template

register = template.Library()

@register.filter
def dia_semana_es(fecha):
    """
    Convierte un objeto date a día de la semana en español
    """
    dias_ingles_espanol = {
        'Monday': 'LUN',
        'Tuesday': 'MAR', 
        'Wednesday': 'MIE',
        'Thursday': 'JUE',
        'Friday': 'VIE',
        'Saturday': 'SAB',
        'Sunday': 'DOM'
    }
    
    # Obtener el nombre del día en inglés
    dia_ingles = fecha.strftime('%A')
    return dias_ingles_espanol.get(dia_ingles, dia_ingles)

@register.filter
def dia_semana_completo_es(fecha):
    """
    Convierte un objeto date a día de la semana completo en español
    """
    dias_ingles_espanol = {
        'Monday': 'Lunes',
        'Tuesday': 'Martes', 
        'Wednesday': 'Miércoles',
        'Thursday': 'Jueves',
        'Friday': 'Viernes',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    
    dia_ingles = fecha.strftime('%A')
    return dias_ingles_espanol.get(dia_ingles, dia_ingles)