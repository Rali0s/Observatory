from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from .engine import analyze
from .darkness import rank
from .models import DraftChapter, Project, Revision

QUIET = 'We drank tea by the window. The black cat slept in the dark room. Tomorrow we would plant flowers.'
HORROR = ("Footsteps came from a room that should have been empty. Something was wrong. "
          "My reflection smiled. It had no eyes and it smiled too wide. "
          "I heard my own voice whispering behind me. There was no escape. "
          "It was coming closer. It was too late. I could not move. "
          "I was no longer myself. Not my memories. Someone was inside my head. "
          "Nobody believed me. I was trapped forever.")


class DarknessEngineTests(SimpleTestCase):
    def test_quiet_prose_and_word_boundaries_do_not_imply_horror(self):
        for text in [QUIET, 'The gorgeous scenery was dreadfully pretty.']:
            report = analyze(text, 'creepypasta')
            self.assertEqual(report['darkness']['level'], 0)
            self.assertFalse(report['darkness']['peaks'])

    def test_psychological_horror_can_rank_high_without_gore(self):
        report = analyze(HORROR, 'creepypasta')
        self.assertGreaterEqual(report['darkness']['level'], 4)
        self.assertEqual(report['scores']['Visceral horror'], 0)
        self.assertIn('Bodily injury', report['darkness']['axes'][-1]['description'])
        self.assertTrue(report['darkness']['short_sample'])
        cues = report['units'][0]['analysis']['evidence']['Darkness']
        self.assertTrue(any(e['cue'] == 'no escape' for e in cues))
        self.assertTrue(all(e['quote'] for e in cues))

    def test_negation_repetition_and_markup(self):
        positive = analyze('There was gore.', 'creepypasta')
        for text in ['There was no gore.', "There wasn't any gore.", 'There was never any gore.']:
            report = analyze(text, 'creepypasta')
            self.assertEqual(report['scores']['Visceral horror'], 0)
            self.assertTrue(report['units'][0]['analysis']['evidence']['Visceral horror'])
        repeated = analyze('Gore. ' * 100, 'creepypasta')
        self.assertLessEqual(repeated['scores']['Visceral horror'], positive['scores']['Visceral horror'])
        self.assertEqual(analyze('# Gore\n\n```\ncorpse\n```\n\n'+QUIET, 'creepypasta')['darkness']['level'], 0)
        self.assertGreater(analyze('The reflection **smiled**.', 'creepypasta')['scores']['Uncanny'], 0)

    def test_chapters_peaks_and_existing_profiles(self):
        report = analyze('# Chapter One\n\n'+QUIET+'\n\n# Chapter Two\n\n'+HORROR, 'creepypasta')
        self.assertEqual(report['darkness']['chapters'][0]['rating']['level'], 0)
        self.assertGreater(report['darkness']['chapters'][1]['rating']['level'], 0)
        self.assertEqual(report['darkness']['peaks'][0]['position'], 2)
        self.assertLess(report['scores']['Darkness'], report['darkness']['peaks'][0]['rating']['score'])
        self.assertIn('creepypasta-1.0', report['engine_version'])
        for profile in ('general', 'river'):
            old = analyze(HORROR, profile)
            self.assertNotIn('darkness', old)
            self.assertNotIn('Darkness', old['scores'])
        self.assertEqual([rank(x)['level'] for x in [0,.01,.15,.35,.55,.75,1]], [0,1,2,3,4,5,5])
        with self.assertRaises(ValueError):
            analyze(HORROR, 'invalid')


class DarknessWorkflowTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('horror-writer')
        self.other = get_user_model().objects.create_user('other-reader')
        self.project = Project.objects.create(owner=self.owner, title='The Empty Room')
        self.client.force_login(self.owner)

    def test_save_inspect_compare_export_and_privacy(self):
        url = reverse('project', args=[self.project.pk])
        self.assertContains(self.client.get(url), 'Creepypasta')
        self.client.post(url, {'label':'Earlier','profile':'general','manuscript':QUIET})
        earlier = self.project.revisions.get()
        response = self.client.post(url, {'label':'Night draft','profile':'creepypasta','manuscript':HORROR})
        self.assertEqual(response.status_code, 302)
        revision = self.project.revisions.get(profile='creepypasta')
        detail = reverse('revision', args=[revision.pk])
        response = self.client.get(detail, {'compare':str(earlier.pk)})
        self.assertContains(response, 'Darkness scale guide')
        self.assertContains(response, 'Darkness across chapters')
        self.assertContains(response, 'No clear signals')
        self.assertContains(response, 'Profiles or engine versions differ')
        self.assertContains(self.client.get(detail, {'signal':'Uncanny'}), 'reflection smiled')
        self.assertContains(self.client.get(reverse('story-aids', args=[revision.pk])), 'Darkness timeline')
        exported = self.client.get(reverse('export-revision', args=[revision.pk])).json()
        self.assertEqual(exported['analysis']['darkness'], revision.analysis['darkness'])
        self.client.force_login(self.other)
        for route in ['revision','story-aids','export-revision','timeline-csv']:
            self.assertEqual(self.client.get(reverse(route,args=[revision.pk])).status_code,404)
        self.assertNotContains(self.client.get(reverse('feed')), 'Night draft')

    def test_chapter_snapshot_profile_and_legacy_report(self):
        DraftChapter.objects.create(project=self.project, title='The voice', markdown=HORROR)
        self.assertContains(self.client.get(reverse('chapters', args=[self.project.pk])), 'Creepypasta')
        response = self.client.post(reverse('chapter-snapshot', args=[self.project.pk]), {'profile':'creepypasta'})
        self.assertEqual(response.status_code,302)
        revision = self.project.revisions.get()
        self.assertIn('darkness', revision.analysis)
        # Previously saved reports are readable and are never silently rescored.
        revision.profile='general';revision.analysis=analyze(QUIET,'general');revision.save()
        self.assertNotContains(self.client.get(reverse('revision',args=[revision.pk])), 'Darkness scale guide')
