# CentroDeEstudios/celery.py
import os
from celery import Celery
from django.conf import settings

# Establecer el módulo de configuración de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CentroDeEstudios.settings')

app = Celery('CentroDeEstudios')

# Configurar Celery usando la configuración de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Cargar tareas automáticamente desde todas las apps registradas
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')