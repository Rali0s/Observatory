import re
from django.core.exceptions import ValidationError

CHANNELS = [
    ('general','General'), ('poetry','Poetry'), ('fiction','Fiction'),
    ('mystery','Mystery'), ('romance','Romance'), ('erotica','Erotica'),
    ('non-fiction','Non-Fiction'), ('memoir','Memoir'), ('fantasy','Fantasy'),
    ('science-fiction','Science Fiction'), ('horror','Horror'),
    ('historical-fiction','Historical Fiction'), ('essays','Essays'),
]


def parse_tags(value):
    tags=[]
    for token in re.split(r'[\s,]+',value.strip()):
        if not token: continue
        name=token.removeprefix('#').casefold()
        if not re.fullmatch(r'[\w][\w-]{0,31}',name):
            raise ValidationError('Use hashtags of 1–32 letters, numbers, underscores or hyphens.')
        if name not in tags: tags.append(name)
    if len(tags)>8: raise ValidationError('Choose up to eight hashtags per publication.')
    return tags


def apply_tags(post,value):
    from .models import Tag
    post.tags.set([Tag.objects.get_or_create(name=name)[0] for name in parse_tags(value)])
