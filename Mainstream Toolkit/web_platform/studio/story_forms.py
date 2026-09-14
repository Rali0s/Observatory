from django import forms
from .models import DraftChapter, StoryEntry


class ChapterForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=0)
    image = forms.FileField(required=False, label='Chapter artwork (PNG/JPEG/WebP, up to 2 MB)')
    remove_art = forms.BooleanField(required=False)

    class Meta:
        model = DraftChapter
        fields = ['title','section','position','markdown','art_alt']
        widgets = {'markdown':forms.Textarea(attrs={'rows':22})}

    def clean_image(self):
        from PIL import Image
        upload = self.cleaned_data['image']
        if upload:
            if upload.size>2000000: raise forms.ValidationError('Artwork must be at most 2 MB.')
            try:
                im = Image.open(upload)
                if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>16000000:
                    raise ValueError()
                self.image_type = Image.MIME[im.format]
                im.verify()
                upload.seek(0)
            except Exception:
                raise forms.ValidationError('Choose a valid PNG, JPEG or WebP image under 16 megapixels.')
        return upload


class EntryForm(forms.ModelForm):
    class Meta:
        model = StoryEntry
        fields = ['kind','title','text','reference','done']
        labels = {'reference':'Chapter, passage, date or story reference','done':'Task complete / fact checked'}
        widgets = {'text':forms.Textarea(attrs={'rows':5})}


class EditionForm(forms.Form):
    title = forms.CharField(max_length=160)
    author = forms.CharField(max_length=160, required=False)
    subtitle = forms.CharField(max_length=160, required=False)
    title_page = forms.CharField(widget=forms.Textarea(attrs={'rows':3}), initial='# {title}\n\n{author}',max_length=8000)
    copyright_page = forms.CharField(widget=forms.Textarea(attrs={'rows':3}), initial='Copyright {copyright_year} {author}\n\nAll rights reserved.',max_length=8000)
    trim_size = forms.ChoiceField(choices=[(x,x) for x in ['5 x 8 in','5.5 x 8.5 in','6 x 9 in','A5','US Letter']],initial='6 x 9 in')
    font_family = forms.ChoiceField(choices=[(x,x) for x in ['Times','Helvetica','Courier']])
    font_size = forms.IntegerField(min_value=8,max_value=24,initial=11)
    line_spacing = forms.FloatField(min_value=1,max_value=2,initial=1.35)
    format = forms.ChoiceField(choices=[('epub','EPUB'),('pdf','PDF'),('md','Markdown')])
