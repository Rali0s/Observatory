from django import template
from django.utils.safestring import mark_safe
from studio.markdown import render_markdown

register = template.Library()

@register.filter
def writing_html(value):
    return mark_safe(render_markdown(value))
