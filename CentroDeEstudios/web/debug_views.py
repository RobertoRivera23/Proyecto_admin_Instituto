from django.http import HttpResponse
from django.shortcuts import render
from web.models import Alumno

def debug_simple(request):
    """View mínima para debug"""
    count = Alumno.objects.filter(eliminado=False).count()
    return HttpResponse(f"🚨 DEBUG: {count} alumnos encontrados")

def debug_template(request):
    """View con template simple"""
    context = {
        'total_alumnos': Alumno.objects.filter(eliminado=False).count(),
        'test_var': 'ESTA VARIABLE DEBERÍA APARECER'
    }
    return render(request, 'debug_simple.html', context)