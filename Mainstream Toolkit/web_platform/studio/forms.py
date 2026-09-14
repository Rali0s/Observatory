from django import forms
from .engine import core
from .models import Project, RevisionNote, AuthorProfile, Publication, Revision
from django.contrib.auth.forms import UserCreationForm
from .taxonomy import parse_tags


class SignupForm(UserCreationForm):
    pen_name = forms.CharField(max_length=80, label='Public pen name')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = AuthorProfile
        fields = ['pen_name', 'bio']
        widgets = {'bio': forms.Textarea(attrs={'rows': 4})}


class PublishForm(forms.ModelForm):
    hashtags = forms.CharField(required=False, max_length=280, label='Hashtags',
        help_text='Up to eight, separated by spaces or commas. Example: #slowburn #foundfamily')
    source_revision = forms.ModelChoiceField(queryset=Revision.objects.none(), required=False,
        label='Related private revision (optional)', help_text='The revision and its analysis stay private.')
    rights_confirmed = forms.BooleanField(label='I have the rights to publish this writing publicly.')

    class Meta:
        model = Publication
        fields = ['title', 'kind', 'channel', 'hashtags', 'excerpt', 'body', 'source_revision']
        widgets = {'body': forms.Textarea(attrs={'rows': 18, 'data-writing-editor': 'true'}), 'excerpt': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_revision'].queryset = Revision.objects.filter(project__owner=user)
        self.fields['source_revision'].label_from_instance = lambda item: f'{item.project.title} · {item.label}'

    def clean_hashtags(self):
        return ' '.join('#'+name for name in parse_tags(self.cleaned_data['hashtags']))


class PublicationCategoryForm(forms.ModelForm):
    hashtags = forms.CharField(required=False, max_length=280, label='Hashtags')

    class Meta:
        model = Publication
        fields = ['channel','hashtags']

    def clean_hashtags(self):
        return ' '.join('#'+name for name in parse_tags(self.cleaned_data['hashtags']))


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title']
        widgets = {'title': forms.TextInput(attrs={'placeholder': 'The Glass Garden'})}


class RevisionForm(forms.Form):
    label = forms.CharField(max_length=160, label='Revision name')
    profile = forms.ChoiceField(choices=Revision._meta.get_field('profile').choices,
        help_text='Choose Creepypasta for a private 0–5 darkness estimate and supporting passages.')
    manuscript = forms.CharField(widget=forms.Textarea(attrs={'rows': 16, 'placeholder': '# Chapter One\n\nYour prose…', 'data-writing-editor': 'true'}),
                                required=False, max_length=500000)
    upload = forms.FileField(required=False, label='Or import a Markdown / text file')

    def __init__(self, *args, max_words=20000, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_words = max_words

    def clean(self):
        cleaned = super().clean()
        manuscript = cleaned.get('manuscript', '')
        upload = cleaned.get('upload')
        if manuscript and upload:
            raise forms.ValidationError('Paste text or choose a file, one at a time.')
        if upload:
            if upload.size > 1024 * 1024 or not upload.name.lower().endswith(('.md', '.markdown', '.txt')):
                raise forms.ValidationError('Import a UTF-8 Markdown or text file smaller than 1 MB.')
            try:
                manuscript = upload.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                raise forms.ValidationError('This file is not UTF-8 text.')
        if not manuscript.strip() or not core.segment(core.split_chapters(manuscript)):
            raise forms.ValidationError('Add manuscript prose before saving.')
        if self.max_words is not None and core.word_count(manuscript) > self.max_words:
            raise forms.ValidationError(f'This pilot supports up to {self.max_words:,} words per revision.')
        cleaned['manuscript'] = manuscript
        return cleaned


class NoteForm(forms.ModelForm):
    class Meta:
        model = RevisionNote
        fields = ['text']
        labels = {'text': 'Revision decision'}
        widgets = {'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What will you revisit in the next draft?'})}
