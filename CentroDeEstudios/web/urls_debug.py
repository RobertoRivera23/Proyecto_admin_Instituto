# web/urls_debug.py
from django.urls import get_resolver
from django.conf import settings

def debug_urls():
    """Imprime todas las URLs registradas para debug"""
    resolver = get_resolver()
    urls = []
    
    def extract_urls(url_patterns, prefix=''):
        for pattern in url_patterns:
            if hasattr(pattern, 'url_patterns'):
                # Es un include
                extract_urls(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                # Es un path
                urls.append({
                    'pattern': prefix + str(pattern.pattern),
                    'name': pattern.name,
                    'callback': pattern.callback.__name__ if callable(pattern.callback) else str(pattern.callback),
                    'module': pattern.callback.__module__ if callable(pattern.callback) else 'N/A'
                })
    
    extract_urls(resolver.url_patterns)
    
    print("=" * 80)
    print("🔍 LISTA COMPLETA DE URLs REGISTRADAS")
    print("=" * 80)
    
    for url in urls:
        print(f"📌 PATTERN: {url['pattern']}")
        print(f"   📝 NAME: {url['name']}")
        print(f"   🎯 VIEW: {url['callback']}")
        print(f"   📦 MODULE: {url['module']}")
        print("-" * 40)

# Para ejecutar: python manage.py shell
# >>> from web.urls_debug import debug_urls
# >>> debug_urls()