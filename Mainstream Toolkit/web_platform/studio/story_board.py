"""Adapted from Unlimited unlimited_lab/workflows.py: portable nodes and typed edges.

Preserves positions, branches, loops and condition/effect provenance. Story cards
replace catalog references; the Unlimited repository is not a runtime dependency.
"""
import math
import json

RELATIONS = ['Sequence','Conflict','Support','Revelation','Dependency','Payoff','Branch']


def text(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Expected text of at most {limit} characters.')
    return value


def validate_board(value):
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ValueError('Expected a version 1 story board.')
    nodes, edges = value.get('nodes'), value.get('edges')
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes)>200 or len(edges)>2000:
        raise ValueError('A board supports 200 scenes and 2,000 connections.')
    ids, clean = set(), []
    for node in nodes:
        if not isinstance(node, dict): raise ValueError('Invalid scene.')
        uid = text(node.get('id'), 80)
        pos = node.get('pos')
        if not uid or uid in ids or not isinstance(pos, list) or len(pos)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=5000 for n in pos):
            raise ValueError('Scenes need unique IDs and positions between 0 and 5,000.')
        ids.add(uid)
        clean.append({'id':uid,'pos':pos, **{k:text(node.get(k,''), 4000 if k in ('goal','conflict','outcome','notes') else 160) for k in ('title','pov','chapter','goal','conflict','outcome','notes')}})
    edge_ids, links = set(), []
    for edge in edges:
        if not isinstance(edge, dict): raise ValueError('Invalid connection.')
        uid = text(edge.get('id'),80)
        if not uid or uid in edge_ids or edge.get('source') not in ids or edge.get('target') not in ids or edge.get('kind') not in RELATIONS:
            raise ValueError('Connections need unique IDs, existing scenes and a known relationship.')
        edge_ids.add(uid)
        links.append({k:edge[k] for k in ('id','source','target','kind')} | {k:text(edge.get(k,''),4000) for k in ('condition','effect','origin')})
    return {'version':1,'name':text(value.get('name','Story board'),120),'nodes':clean,'edges':links}


def validate_mapping(value):
    if not isinstance(value,dict) or len(value)>100:
        raise ValueError('Use an object with at most 100 names.')
    for name, aliases in value.items():
        if not text(name,120).strip() or not isinstance(aliases,list) or not 1<=len(aliases)<=20:
            raise ValueError('Each name needs 1–20 aliases.')
        for alias in aliases:
            if not text(alias,120).strip(): raise ValueError('Aliases cannot be empty.')
    return value


def parse_vocabulary(value):
    if value.strip().startswith('{'): return validate_mapping(json.loads(value))
    mapping={}
    for line in value.splitlines():
        if not line.strip(): continue
        name,sep,rest=line.partition(':')
        if not sep: raise ValueError('Use one entry per line: Ada: Ada, the mapmaker')
        mapping[name.strip()]=[a.strip() for a in rest.split(',') if a.strip()]
    return validate_mapping(mapping)


def vocabulary_text(value):
    return '\n'.join(f'{name}: '+', '.join(aliases) for name,aliases in value.items())
