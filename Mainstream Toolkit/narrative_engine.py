"""Independent, evidence-bearing narrative estimates. No overall sentiment score."""
from __future__ import annotations
import hashlib
import math
import re
from collections import defaultdict

VERSION = '1.0'
# Low and high anchors are definitions, not mutually exclusive categories.
SIGNALS = {
 'Thrill': ('calm/stable', 'danger, uncertainty, pursuit', 'danger|pursuit|chased|escape|ambush|gunfire|fled'),
 'Excitement': ('subdued', 'energy, anticipation', 'eager|rushed|cheered|exhilarated|anticipation|racing|could not wait'),
 'Love': ('detachment', 'devotion, attachment', 'devotion|beloved|cherished|adored|loved|love|loyalty'),
 'Kindness': ('indifference', 'care, generosity, protection', 'comforted|sheltered|protected|forgave|generosity|helped|kindness'),
 'Cruelty': ('compassion', 'deliberate suffering, dehumanization', 'tortured|humiliated|tormented|dehumanized|deliberately hurt|enjoyed their suffering|cruelty'),
 'Epic': ('personal/local', 'civilization or cosmic consequence', 'civilization|humanity|universe|cosmos|extinction|generations|worlds'),
 'Wonder': ('ordinary', 'awe, revelation, sublime', 'awe|marvel|sublime|wondrous|revelation|astonished|impossible beauty'),
 'Dread': ('security', 'approaching unavoidable threat', 'dread|inevitable|doom|no escape|too late|approaching threat|would not survive'),
 'Mystery': ('explicit', 'withheld or contradictory information', 'secret|unexplained|unknown|contradiction|riddle|impossible|who had'),
 'Grief': ('continuity', 'loss, absence', 'grief|mourned|loss|bereft|funeral|never returned|missed her|missed him'),
 'Hope': ('resignation', 'possibility, future orientation', 'hope|tomorrow|possibility|another chance|could still|a future|begin again'),
 'Conflict': ('agreement', 'incompatible objectives', 'refused|opposed|argued|enemy|disagreed|fight|incompatible'),
 'Philosophical': ('concrete action', 'ontological or ethical questioning', 'existence|consciousness|meaning|ethics|free will|what is real|ought|moral|truth'),
 'Identity': ('stable self', 'selfhood questioned or transformed', 'who am i|who was she|who was he|selfhood|identity|no longer myself|became someone'),
 'Sacrifice': ('self-preservation', 'cost accepted for another or cause', 'sacrificed|gave up|at the cost|in her place|in his place|save them|accepted the cost'),
 'Agency': ('passive', 'consequential choice', 'chose|decided|resolved|refused|took responsibility|i will|choice'),
 'Intimacy': ('interpersonal distance', 'emotional closeness', 'confided|trusted|shared her secret|shared his secret|held her|held him|vulnerable|intimacy'),
 'Isolation': ('belonging', 'separation, alienation', 'alone|isolated|alienated|nobody|exiled|abandoned|stranger|belonged nowhere'),
}
MECHANISMS = {
 'DRAGON': ('emergence', 'dragon|emergence|arose|awakening'),
 'BIRD': ('transformation', 'bird|transformation|metamorphosis|reborn'),
 'TIGER': ('dissolution', 'tiger|dissolution|dissolved|unravelled'),
 'TORTOISE': ('persistence', 'tortoise|persistence|endured|persisted'),
 'ZERO': ('absence-boundary', 'zero|absence|boundary|nothingness'),
 'RIVER': ('continuity-through-change', 'river|current|continuity|flowed'),
 'PERCIVAL': ('custodianship', 'percival|custodian|custodianship|steward'),
 'SHARD': ('distributed inheritance', 'shard|fragments|inheritance|distributed'),
 'RESET_HINT': ('discontinuity symptoms', ''),
 'AI_SENTIENCE': ('synthetic subjectivity', 'sentient machine|artificial consciousness|synthetic mind|machine felt|synthetic subjectivity'),
 'WAR_PROGRESS': ('civilization choice', 'war|peace|progress|civilization chose|arms race'),
}
SYMPTOMS = {
 'Discontinuity': 'missing hour|missing day|time skipped|discontinuity|clock jumped',
 'Déjà vu': 'déjà vu|deja vu|happened before|again for the first time',
 'Contradictory memory': 'remembered differently|two memories|contradictory memories|could not remember',
 'Altered relationships': 'did not recognize|no longer knew|strangers yesterday',
 'Impossible knowledge': 'knew before|remembered tomorrow|memory of the future|had not yet happened',
 'Temporal language': 'yesterday was different|time reversed|another timeline|before this life',
}
DEFAULT_CLUES = {
 'Nursery rhyme': ['nursery rhyme'], 'River': ['river'], 'Dreamers': ['dreamers'],
 'Mirror Shard': ['mirror shard'], 'Chinese Tomb': ['chinese tomb'],
 'Four Houses': ['four houses', 'dragon', 'bird', 'tiger', 'tortoise'],
 'Midpoint discontinuities': [x for v in SYMPTOMS.values() for x in v.split('|')],
}


def matches(text, terms):
    return list(re.finditer(r'(?<!\w)(?:' + '|'.join(re.escape(t) for t in terms if t) + r')(?!\w)', text, re.I)) if terms else []


def word_count(text):
    return len(re.findall(r"\b\w+(?:['’]\w+)*\b", text))


def prose(text):
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    text = re.sub(r'^#{1,6} .*$', '', text, flags=re.M)
    return re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', text).strip()


def analyze_passage(text, river=True):
    clean = prose(text)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n\s*\n', clean) if s.strip()]
    definitions = {k: v[2] for k, v in SIGNALS.items()}
    if river:
        definitions.update({k: v[1] for k, v in MECHANISMS.items() if k != 'RESET_HINT'})
        definitions.update(SYMPTOMS)
    scores, evidence = {}, {}
    for signal, cues in definitions.items():
        mass, reasons = 0., []
        for sentence in sentences:
            hits = matches(sentence, cues.split('|'))
            for hit in hits:
                prefix = sentence[max(0, hit.start()-35):hit.start()]
                negated = bool(re.search(r"\b(?:not|never|no|without|neither)\b(?:\W+\w+){0,3}\W*$", prefix, re.I))
                weight = .15 if negated else 1.
                # A question alone is not philosophy; syntax only amplifies a grounded cue.
                syntax = .15 if signal in ('Philosophical', 'Mystery', 'Identity') and '?' in sentence else 0.
                mass += weight + (0 if negated else syntax)
                reasons.append({'quote': sentence, 'cue': hit.group(), 'reason':
                    'Negated cue; reduced weight (scope is approximate).' if negated else
                    'Lexical cue' + (' with interrogative syntax.' if syntax else '; interpretation needs context.')})
        scores[signal] = round(1-math.exp(-mass/max(2., word_count(clean)/65)), 3)
        evidence[signal] = reasons
    if river:
        scores['RESET_HINT'] = round(1-math.prod(1-scores[k] for k in SYMPTOMS), 3)
        evidence['RESET_HINT'] = [dict(e, reason=k+': '+e['reason']) for k in SYMPTOMS for e in evidence[k]]
    return {'scores': scores, 'evidence': evidence, 'words': word_count(clean), 'method': 'offline lexical + syntax', 'version': VERSION}


def split_chapters(text, title='Manuscript'):
    pattern = r'(?im)^(?:#{1,2}\s+chapter\b[^\n]*|chapter\s+(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)\b[^\n]*)$'
    headings = list(re.finditer(pattern, text))
    if not headings:
        return [(title, text)] if text.strip() else []
    result = [(title+' · Preface', text[:headings[0].start()])] if text[:headings[0].start()].strip() else []
    for i, heading in enumerate(headings):
        end = headings[i+1].start() if i+1 < len(headings) else len(text)
        result.append((heading.group().lstrip('# ').strip(), text[heading.end():end].strip()))
    return result


def segment(chapters):
    units = []
    for ci, (title, text) in enumerate(chapters):
        scenes = re.split(r'(?m)^\s*(?:\*\s*\*\s*\*|---+|___+)\s*$|^#{2,6}\s+[^\n]+$', text)
        for si, scene in enumerate(scenes):
            for pi, passage in enumerate(re.split(r'\n\s*\n', scene)):
                passage = passage.strip()
                if not prose(passage):
                    continue
                uid = hashlib.sha256(f'{ci}:{si}:{pi}:{passage}'.encode()).hexdigest()[:16]
                units.append({'id': uid, 'chapter': title, 'chapter_index': ci, 'scene': si+1,
                              'passage': pi+1, 'text': passage, 'position': len(units)+1})
    total = sum(word_count(u['text']) for u in units)
    consumed = 0
    for u in units:
        u['narrative_position'] = round(consumed/max(1,total), 4)
        consumed += word_count(u['text'])
    return units


def aggregate(units, level):
    groups = defaultdict(list)
    for u in units:
        key = ('Manuscript',) if level == 'Manuscript' else ((u['chapter_index'],) if level == 'Chapter' else (u['chapter_index'],u['scene']) if level == 'Scene' else (u['id'],))
        groups[key].append(u)
    result = []
    for i, members in enumerate(groups.values()):
        first = members[0]
        weights = [max(1,m['analysis']['words']) for m in members]
        scores = {k: round(sum(m['analysis']['scores'][k]*w for m,w in zip(members, weights))/sum(weights),3) for k in first['analysis']['scores']}
        label = 'Manuscript' if level == 'Manuscript' else f"{first['chapter_index']+1}. {first['chapter']}"
        if level in ('Scene', 'Passage'): label += f" · scene {first['scene']}"
        if level == 'Passage': label += f" · passage {first['passage']}"
        result.append({'order': i+1, 'label': label, 'scores': scores, 'members': members})
    return result


def character_traces(units, roster):
    rows, relationships = [], []
    for u in units:
        present = [name for name, aliases in roster.items() if matches(u['text'], [name,*aliases])]
        for name in present:
            rows.append({'character': name, 'position': u['position'], 'chapter': u['chapter'], **{k:u['analysis']['scores'][k] for k in SIGNALS}})
        for i, name in enumerate(present):
            for other in present[i+1:]:
                relationships.append({'character': name, 'other': other, 'position': u['position'], 'quote': u['text']})
    return rows, relationships


def clue_trails(units, clues, annotations):
    rows = []
    for clue, aliases in clues.items():
        occurrences = [u for u in units if matches(u['text'], aliases)]
        for i, u in enumerate(occurrences):
            saved = annotations.get(clue+'::'+u['id'], {})
            rows.append({'clue': clue, 'id': u['id'], 'position': u['position'], 'chapter': u['chapter'],
                         'status': saved.get('status', 'Candidate plant' if i == 0 else 'Recurrence'),
                         'note': saved.get('note',''), 'quote': u['text']})
    return rows


def debt_timeline(units, trails):
    state, rows = {}, []
    for u in units:
        for event in (t for t in trails if t['id']==u['id']):
            status = event['status']
            if status == 'Planted': state[event['clue']] = u['position']
            elif status in ('Paid off', 'Abandoned'): state.pop(event['clue'], None)
        rows.append({'position':u['position'], 'open_clues':len(state), 'age_in_passages':sum(u['position']-p for p in state.values())})
    return rows
