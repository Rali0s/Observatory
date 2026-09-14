from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from .engine import analyze, core
from .models import AccessGrant, Project, Revision, RevisionNote

PROSE = '# Chapter One\n\nMara chose to help Elias. Hope for tomorrow.\n\n# Chapter Two\n\nDread. No escape.'


class WorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('author', password='a-test-passphrase-392!')
        cls.other = get_user_model().objects.create_user('other', password='a-test-passphrase-487!')
        cls.grant = AccessGrant.objects.create(user=cls.owner)
        cls.project = Project.objects.create(owner=cls.owner, title='A Private Manuscript')

    def setUp(self):
        self.client.force_login(self.owner)

    def save_revision(self, text=PROSE, label='First draft'):
        response = self.client.post(reverse('project', args=[self.project.pk]),
            {'label': label, 'profile': 'general', 'manuscript': text})
        self.assertEqual(response.status_code, 302)
        return Revision.objects.latest('created_at')

    def test_complete_revision_and_export_flow(self):
        first = self.save_revision()
        second = self.save_revision(PROSE + '\n\nShe hoped for another chance.', 'Second draft')
        first.refresh_from_db()
        self.assertEqual(first.manuscript, PROSE)
        response = self.client.get(reverse('revision', args=[second.pk]), {'compare': first.pk, 'signal': 'Hope'})
        self.assertContains(response, 'Read the evidence')
        self.assertContains(response, 'First draft')
        self.assertIn('no-store', response['Cache-Control'])
        self.client.post(reverse('add-note', args=[second.pk]), {'text': 'Let the final scene breathe.'})
        exported = self.client.get(reverse('export-revision', args=[second.pk])).json()
        self.assertEqual(exported['notes'][0]['text'], 'Let the final scene breathe.')
        self.assertEqual(exported['analysis']['method'], 'offline lexical + syntax')

    def test_every_manuscript_endpoint_checks_owner(self):
        revision = self.save_revision()
        self.client.force_login(self.other)
        for name, identifier in [('project', self.project.pk), ('revision', revision.pk), ('export-revision', revision.pk)]:
            self.assertEqual(self.client.get(reverse(name, args=[identifier])).status_code, 404)
        self.assertEqual(self.client.post(reverse('project', args=[self.project.pk]),
            {'label': 'Intrusion', 'profile': 'general', 'manuscript': PROSE}).status_code, 404)
        self.assertEqual(self.client.post(reverse('add-note', args=[revision.pk]), {'text': 'Intrusion'}).status_code, 404)
        self.assertEqual(RevisionNote.objects.count(), 0)
        self.assertNotContains(self.client.get(reverse('library')), self.project.title)

    def test_compare_cannot_cross_project(self):
        revision = self.save_revision()
        different = Project.objects.create(owner=self.other, title='Other book')
        baseline = Revision.objects.create(project=different, label='Hidden', manuscript=PROSE,
            profile='general', fingerprint='x'*64, word_count=20, engine_version='1.0', analysis=analyze(PROSE, 'general'))
        response = self.client.get(reverse('revision', args=[revision.pk]), {'compare': baseline.pk})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(reverse('revision', args=[revision.pk]), {'compare': 'invalid'}).status_code, 404)

    def test_expired_legacy_grant_does_not_lock_free_tools(self):
        revision = self.save_revision()
        self.grant.expires_at = timezone.now() - timedelta(seconds=1)
        self.grant.save()
        self.assertEqual(self.client.post(reverse('project', args=[self.project.pk]),
            {'label': 'Free revision', 'profile': 'general', 'manuscript': PROSE}).status_code, 302)
        self.assertEqual(self.client.post(reverse('library'), {'title': 'Free project'}).status_code, 302)
        self.assertEqual(self.client.get(reverse('export-revision', args=[revision.pk])).status_code, 200)

    def test_project_and_word_allowances(self):
        self.grant.max_projects = 1
        self.grant.max_words_per_revision = 3
        self.grant.save()
        self.assertContains(self.client.post(reverse('library'), {'title': 'Too many'}), 'allowance is full')
        self.assertEqual(Project.objects.filter(owner=self.owner).count(), 1)
        response = self.client.post(reverse('project', args=[self.project.pk]),
            {'label': 'Too long', 'profile': 'general', 'manuscript': PROSE})
        self.assertContains(response, 'up to 3 words')
        self.assertEqual(Revision.objects.count(), 0)

    def test_no_grant_needed_for_free_tools(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('library'), {'title': 'Free access'}).status_code, 302)

    def test_utf8_upload_and_html_are_safe(self):
        response = self.client.post(reverse('project', args=[self.project.pk]), {
            'label': 'Élan', 'profile': 'general',
            'upload': SimpleUploadedFile('draft.md', '# Chapter One\n\nHope. <script>alert(1)</script>'.encode())})
        self.assertEqual(response.status_code, 302)
        revision = Revision.objects.get()
        response = self.client.get(reverse('revision', args=[revision.pk]))
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_empty_and_binary_uploads_rejected(self):
        for upload in [SimpleUploadedFile('bad.md', b'\xff\xfe'), SimpleUploadedFile('only-headings.md', b'# Chapter One')]:
            response = self.client.post(reverse('project', args=[self.project.pk]),
                {'label': 'Bad', 'profile': 'general', 'upload': upload})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(Revision.objects.count(), 0)

    def test_csrf_and_anonymous_access(self):
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.owner)
        self.assertEqual(strict_client.post(reverse('library'), {'title': 'No token'}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('project', args=[self.project.pk])).status_code, 302)

    def test_adapter_matches_existing_engine(self):
        report = analyze(PROSE, 'general')
        units = core.segment(core.split_chapters(PROSE))
        for unit in units:
            unit['analysis'] = core.analyze_passage(unit['text'], river=False)
        self.assertEqual(report['scores'], core.aggregate(units, 'Manuscript')[0]['scores'])
