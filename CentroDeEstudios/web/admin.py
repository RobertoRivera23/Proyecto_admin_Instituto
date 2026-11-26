from django.contrib import admin
from .models import Curso, Profesor, Personal, PasswordChangeLog
# NO necesitas importar o registrar los modelos de django_celery_beat
# from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule  # <-- COMENTA O ELIMINA
# from django_celery_beat.admin import PeriodicTaskAdmin, PeriodicTaskForm  # <-- COMENTA O ELIMINA

# Registrar modelos básicamente sin personalizaciones
admin.site.register(Curso)
admin.site.register(Profesor)
admin.site.register(Personal)

# NO registrar modelos de Celery Beat porque ya están registrados por django_celery_beat
# admin.site.register(IntervalSchedule)  # <-- COMENTA O ELIMINA
# admin.site.register(CrontabSchedule)   # <-- COMENTA O ELIMINA
# admin.site.register(PeriodicTask)      # <-- COMENTA O ELIMINA


@admin.register(PasswordChangeLog)
class PasswordChangeLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'changed_at', 'changed_by', 'ip_address')
    list_filter = ('changed_at', 'user', 'changed_by')
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('changed_at', 'user', 'changed_by', 'ip_address', 'user_agent')
    date_hierarchy = 'changed_at'
    
    def has_add_permission(self, request):
        return False  # No permitir crear registros manualmente
    
    def has_change_permission(self, request, obj=None):
        return False  # No permitir editar registros
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Solo superusuarios pueden eliminar