"""Temporary adapter: reuse the existing pure Python engine without copying it.

Ship the enclosing Mainstream Toolkit directory until this becomes a versioned package.
No Streamlit import and no network calls occur here.
"""
import hashlib
import importlib.util
from pathlib import Path
from . import darkness

ENGINE_PATH = Path(__file__).resolve().parents[2] / 'narrative_engine.py'
spec = importlib.util.spec_from_file_location('observatory_narrative_core', ENGINE_PATH)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def analyze(manuscript, profile):
    if profile not in ('general', 'river', 'creepypasta'):
        raise ValueError('Choose a valid analysis profile.')
    chapters = core.split_chapters(manuscript)
    units = core.segment(chapters)
    if not units:
        raise ValueError('Add prose beneath your chapter headings before saving.')
    for unit in units:
        unit['analysis'] = core.analyze_passage(unit['text'], river=profile == 'river')
        if profile == 'creepypasta':
            scores, evidence = darkness.analyze_passage(core.prose(unit['text']), unit['analysis']['words'])
            unit['analysis']['scores'].update(scores)
            unit['analysis']['evidence'].update(evidence)
            unit['analysis']['version'] += '+' + darkness.VERSION
    groups = core.aggregate(units, 'Chapter')
    report = {
        'schema_version': 1, 'engine_version': core.VERSION,
        'method': 'offline lexical + syntax', 'profile': profile,
        'word_count': sum(u['analysis']['words'] for u in units),
        'scores': core.aggregate(units, 'Manuscript')[0]['scores'],
        'chapters': [{'label': g['label'], 'scores': g['scores']} for g in groups],
        'units': units,
    }
    if profile == 'creepypasta':
        report['engine_version'] += '+' + darkness.VERSION
        report['darkness'] = darkness.summarize(report)
    return report


def fingerprint(manuscript, profile):
    return hashlib.sha256((profile + '\0' + manuscript).encode('utf-8')).hexdigest()
