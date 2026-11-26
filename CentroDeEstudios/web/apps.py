from django.apps import AppConfig


class WebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'web'
    
    def ready(self):
        """
        Este método se ejecuta cuando la app está lista
        Aquí importamos y registramos las señales
        """
        # Importar las señales
        import web.signals
        print("✅ Señales de backup automático cargadas correctamente")
        
        

class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'  # cambia por el nombre de tu app
    
    def ready(self):
        import usuarios.signals  # cambia por el nombre de tu app