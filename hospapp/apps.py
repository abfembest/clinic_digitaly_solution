from django.apps import AppConfig
from django import template


class HospappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hospapp'


register = template.Library()

@register.filter
def get_status_color(status_code):
    color_map = {
        'pending': 'warning',
        'completed': 'success',
        'in_progress': 'info',
        'cancelled': 'danger',
        'Admitted': 'primary',
        'Discharged': 'success',
        'critical': 'danger',
        'stable': 'success',
        'partial': 'warning',
        'paid': 'success',
    }
    return color_map.get(status_code, 'secondary')
