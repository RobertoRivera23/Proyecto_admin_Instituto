# Proyecto Admin Instituto

Proyecto de gestión escolar basado en Django + PostgreSQL + Redis + Celery.

## Stack
- Django
- PostgreSQL
- Redis + Celery
- Python 3.14 (con parches de compatibilidad)

## Configuración local
1. Crear `envs/.env` con las variables necesarias (ver `.env.example` si existe).
2. `pip install -r requirements.txt`
3. `python manage.py migrate`
4. `python manage.py runserver`

## Origen
Idea IACL