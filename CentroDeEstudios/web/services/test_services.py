# web/services/test_services.py
from .notificaciones_service import ServicioNotificaciones

def test_servicios():
    print("🧪 Probando servicios de notificaciones...")
    
    # Crear tipos de notificación
    ServicioNotificaciones.crear_tipos_notificacion()
    print("✅ Tipos de notificación creados")
    
    # Generar notificaciones automáticas
    ServicioNotificaciones.generar_notificaciones_automaticas()
    print("✅ Notificaciones automáticas generadas")