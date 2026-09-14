"""Offline English horror cues. An editorial aid, not a reader or age rating."""
import math
import re
from collections import Counter

VERSION = 'creepypasta-1.0'
AXES = {
    'Creeping unease': (
        'A familiar place begins to feel wrong.',
        'watched me|watching me|being watched|behind me|footsteps|scratching at|whispering|whispered my name|something was wrong|something felt wrong|should have been empty|door was open|breathing in the dark|flickering|unsettling',
        'Try a small change in a familiar routine, then let the narrator notice it.'),
    'Creeping dread': (
        'An approaching threat and narrowing ways out.',
        'dread|no escape|could not escape|couldn’t escape|could not get out|too late|coming closer|getting closer|would not survive|would never leave|could not move|couldn’t move|locked from outside|do not turn around|don’t turn around|nowhere to hide',
        'Give the threat a consequence, and make each attempt to get safe cost something.'),
    'Uncanny': (
        'Impossible events, doubles, and broken rules of reality.',
        'reflection moved|reflection smiled|not my reflection|without a face|faceless|wrong number of|voice of my dead|dead mother’s voice|dead mother\'s voice|my own voice|not human|inhuman|impossible angle|impossible angles|empty eye sockets|no eyes|smiled too wide|time stopped|same dream',
        'Establish one ordinary rule before showing the reader exactly how it breaks.'),
    'Psychological horror': (
        'Threats to memory, identity, trust, or control.',
        'losing my mind|could not trust|couldn’t trust|cannot trust|can’t trust|not my memories|memories were not mine|no longer myself|forgot my name|erased my memories|inside my head|paranoia|hallucination|hallucinations|tormented|helpless|trapped forever|nobody believed me',
        'Show the narrator testing their perception, and what happens when the test fails.'),
    'Visceral horror': (
        'Bodily injury and graphic physical horror.',
        'gore|gory|guts|entrails|dismembered|severed|mutilated|rotting flesh|exposed bone|exposed bones|skin peeled|peeled skin|torn flesh|blood pooled|blood pooling|blood soaked|blood-soaked|corpse|corpses',
        'Choose physical detail deliberately. More gore is not required for a darker story.'),
}
LEVELS = [
    (0, 'No clear signals', 'No supported horror cues found; subtle horror can still be present.'),
    (1, 'Unsettling', 'Light unease or a few disturbing details.'),
    (2, 'Eerie', 'A noticeable sense that something is wrong.'),
    (3, 'Disturbing', 'Repeated threats, uncanny events, or unsettling implications.'),
    (4, 'Terrifying', 'Strong horror signals across the passage or draft.'),
    (5, 'Nightmarish', 'Dense, overlapping horror signals.'),
]


def rank(score):
    level = 0 if score == 0 else 1 if score < .15 else 2 if score < .35 else 3 if score < .55 else 4 if score < .75 else 5
    number, label, description = LEVELS[level]
    return {'level': number, 'label': label, 'description': description, 'score': score}


def analyze_passage(clean, words):
    # Ignore markup decoration; keep the quoted evidence in the author's own words.
    clean = re.sub(r'[*_`~]', '', clean).replace('’', "'")
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n\s*\n', clean) if s.strip()]
    scores, evidence = {}, {}
    for name, (_, cues, _) in AXES.items():
        pattern = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(c.replace('’', "'")) for c in cues.split('|')) + r')(?!\w)', re.I)
        counts, reasons = Counter(), []
        for sentence in sentences:
            for hit in pattern.finditer(sentence):
                prefix = sentence[max(0, hit.start()-45):hit.start()]
                negated = bool(re.search(r"\b(?:not|never|no|without|neither|wasn't|weren't|isn't|aren't|didn't)\b(?:\W+\w+){0,3}\W*$", prefix, re.I))
                cue = hit.group().lower()
                if not negated:
                    counts[cue] += 1
                # Bound storage and avoid repeated evidence filling the report.
                if len(reasons) < 8 and not any(e['quote'] == sentence and e['cue'].lower() == cue for e in reasons):
                    reasons.append({'quote': sentence, 'cue': hit.group(), 'reason':
                        'Negated cue; excluded from this estimate. Negation scope is approximate.' if negated else
                        f'{name} cue; review its meaning in context.'})
        # A repeated keyword alone cannot push a passage up the scale.
        mass = len(counts)
        scores[name] = round(1 - math.exp(-mass / max(2., words / 80)), 3)
        evidence[name] = reasons
    # The strongest dimension matters most; psychological horror needs no gore.
    scores['Darkness'] = round(.65 * max(scores.values()) + .35 * sum(scores.values()) / len(AXES), 3)
    evidence['Darkness'] = [dict(e, reason=name + ': ' + e['reason']) for name in AXES for e in evidence[name]]
    return scores, evidence


def summarize(report):
    overall = rank(report['scores']['Darkness'])
    overall.update(version=VERSION, short_sample=report['word_count'] < 100,
        axes=[{**rank(report['scores'][name]), 'name': name, 'description': description, 'tip': tip}
              for name, (description, _, tip) in AXES.items()],
        scale=[{'level': n, 'label': label, 'description': description} for n, label, description in LEVELS],
        chapters=[{'label': chapter['label'], 'rating': rank(chapter['scores']['Darkness'])} for chapter in report['chapters']],
        peaks=[{'position': unit['position'], 'chapter': unit['chapter'], 'rating': rank(unit['analysis']['scores']['Darkness'])}
               for unit in sorted(report['units'], key=lambda u: u['analysis']['scores']['Darkness'], reverse=True)[:3]
               if unit['analysis']['scores']['Darkness'] > 0])
    return overall
