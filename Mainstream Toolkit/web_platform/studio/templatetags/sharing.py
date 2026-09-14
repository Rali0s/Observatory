from urllib.parse import urlencode
from django import template
from django.conf import settings
from django.urls import reverse

register = template.Library()

@register.simple_tag(takes_context=True)
def publication_url(context, post):
    path = reverse('read', args=[post.pk])
    base = settings.PUBLIC_BASE_URL.rstrip('/')
    return base + path if base else context['request'].build_absolute_uri(path)

@register.inclusion_tag('community/social_share.html', takes_context=True)
def social_share(context, post):
    if not post.is_visible:
        return {}
    url = publication_url(context, post)
    links = [
        ('x', 'X', 'https://x.com/intent/tweet?' + urlencode({'text': post.title, 'url': url})),
        ('facebook', 'Facebook', 'https://www.facebook.com/sharer/sharer.php?' + urlencode({'u': url})),
        ('blogger', 'Blogger', 'https://www.blogger.com/blog-this.g?' + urlencode({'u': url, 'n': post.title, 't': post.excerpt})),
        ('linkedin', 'LinkedIn', 'https://www.linkedin.com/sharing/share-offsite/?' + urlencode({'url': url})),
    ]
    return {'share_links': links, 'share_url': url, 'share_title': post.title}
