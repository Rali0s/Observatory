from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import AuthorProfile, Project, Publication
from .markdown import render_markdown
from .forms import RevisionForm, PublishForm
from .story_forms import ChapterForm, EditionForm

class WritingEditorTests(TestCase):
    def test_writing_fields_offer_editor_without_changing_submitted_format(self):
        user=get_user_model().objects.create_user('writer')
        for form,fields in [(RevisionForm(),['manuscript']),(PublishForm(user=user),['body']),
            (ChapterForm(),['markdown']),(EditionForm(),['title_page','copyright_page'])]:
            for name in fields:
                self.assertIn('data-writing-editor',form.fields[name].widget.attrs)

    def test_public_formatting_and_html_sanitization(self):
        body='# Title\n\n## Scene\n\n### Beat\n\n**Bold** and *italic*.\n\n- First\n- Second\n\n> A quote\n\n<script>alert(1)</script><img src=x onerror=alert(1)>'
        html=render_markdown(body)
        for tag in ['h1','h2','h3','strong','em','ul','blockquote']:
            self.assertIn('<'+tag+'>',html)
        self.assertNotIn('<script',html)
        self.assertNotIn('<img',html)
        author=AuthorProfile.objects.create(user=get_user_model().objects.create_user('author'),pen_name='An author')
        post=Publication.objects.create(author=author,title='Formatting',excerpt='Preview',body=body,kind='story')
        response=self.client.get(reverse('read',args=[post.pk]))
        self.assertContains(response,'<strong>Bold</strong>')
        self.assertNotContains(response,'<script>alert(1)</script>')

    def test_chapter_save_keeps_markdown_and_editor_is_present(self):
        user=get_user_model().objects.create_user('writer')
        project=Project.objects.create(owner=user,title='Book')
        self.client.force_login(user)
        body='## Scene\n\n**Bold** and *italic*.\n\n> Quote'
        url=reverse('chapters',args=[project.pk])
        response=self.client.post(url,{'title':'Opening','position':1,'markdown':body,'version':0})
        self.assertEqual(response.status_code,302)
        chapter=project.draft_chapters.get()
        self.assertEqual(chapter.markdown,body)
        response=self.client.get(reverse('chapter-edit',args=[project.pk,chapter.pk]))
        self.assertContains(response,'writing-editor.')
        self.assertContains(response,'<strong>Bold</strong>')
