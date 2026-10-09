"""Validate the shipped design fixtures, not actual media or a renderer.

Uses stdlib only. The structural checker covers exactly the JSON Schema keywords
used by contracts.schema.json; it is not a general Draft 2020-12 implementation.
Production should use jsonschema/Pydantic plus the documented semantic checks.
Run: python3 validate_examples.py
"""
from pathlib import Path
from copy import deepcopy
import json
import math
import re

ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / 'contracts.schema.json').read_text())

def need(condition, message):
    if not condition:
        raise ValueError(message)

def structural(value, spec, path='$'):
    if '$ref' in spec:
        structural(value, SCHEMA['$defs'][spec['$ref'].split('/')[-1]], path)
        return
    for combiner in ('oneOf', 'anyOf'):
        if combiner in spec:
            matches=0
            for sub in spec[combiner]:
                try:
                    structural(value, sub, path)
                    matches += 1
                except ValueError:
                    pass
            need(matches == 1 if combiner == 'oneOf' else matches >= 1,
                 f'{path}: {combiner} matched {matches} branches')
    if 'const' in spec:
        need(type(value) is type(spec['const']) and value == spec['const'], f'{path}: const')
    if 'enum' in spec:
        need(any(type(value) is type(x) and value == x for x in spec['enum']), f'{path}: enum')
    t=spec.get('type')
    if t:
        valid={'object':isinstance(value,dict),'array':isinstance(value,list),
               'string':isinstance(value,str),'integer':type(value) is int,
               'number':type(value) in (int,float),'boolean':type(value) is bool,'null':value is None}
        need(valid[t], f'{path}: expected {t}')
    if isinstance(value,dict):
        props=spec.get('properties',{})
        need(set(spec.get('required',[])) <= value.keys(), f'{path}: missing required fields')
        if spec.get('additionalProperties') is False:
            need(value.keys() <= props.keys(), f'{path}: unknown fields')
        for key,item in value.items():
            if key in props:structural(item,props[key],path+'.'+key)
    elif isinstance(value,list):
        need(len(value)>=spec.get('minItems',0), f'{path}: minItems')
        if spec.get('uniqueItems'):
            need(len({json.dumps(x,sort_keys=True) for x in value})==len(value),f'{path}: duplicate items')
        if 'items' in spec:
            for i,item in enumerate(value):structural(item,spec['items'],f'{path}[{i}]')
    elif isinstance(value,str):
        need(len(value)>=spec.get('minLength',0) and len(value)<=spec.get('maxLength',math.inf),f'{path}: string length')
        if 'pattern' in spec:need(re.search(spec['pattern'],value) is not None,f'{path}: pattern')
    elif type(value) in (int,float):
        need(math.isfinite(value),f'{path}: non-finite number')
        need(spec.get('minimum',-math.inf)<=value<=spec.get('maximum',math.inf),f'{path}: range')

def unique(items,key):
    need(len({x[key] for x in items})==len(items),f'duplicate {key}')

def check_assets(doc):
    unique(doc['assets'],'asset_id')
    for a in doc['assets']:
        need(all(part not in ('','.','..') for part in a['storage_key'].split('/')),'invalid storage key')
    return {a['asset_id']:a for a in doc['assets']}

def asset(assets,aid,kinds):
    need(aid in assets,f'missing asset {aid}')
    need(assets[aid]['kind'] in kinds,f'wrong kind for {aid}')
    return assets[aid]

def check_output(o):
    need((o['width'],o['height']) in ((1280,720),(720,1280)),'unsupported resolution')

def check_plan(doc,assets):
    p=doc['plan'];unique(p['shots'],'shot_id');unique(p['sections'],'section_id')
    sections={x['section_id'] for x in p['sections']}
    for shot in p['shots']:
        a=asset(assets,shot['clip_id'],['video']);w=shot['source_window']
        need(0<=w['in_seconds']<w['out_seconds']<=a['duration_seconds'],'invalid candidate range')
        need(shot['preferred_duration_seconds']<=w['out_seconds']-w['in_seconds'],'preferred duration outside window')
        need(shot['section_id'] is None or shot['section_id'] in sections,'unknown section')

def check_rect(b,o):
    need(b['x']+b['width']<=o['width'] and b['y']+b['height']<=o['height'],'rectangle outside output')

def check_timeline(doc,assets,supported=None,transcripts=None):
    t=doc['timeline'];o=t['output'];check_output(o);fps=o['fps'];length=t['duration_frames']
    need(doc['version_id']!=doc['parent_version_id'],'version is its own parent')
    caps=set(t['required_capabilities'])
    need('core_v1' in caps,'missing core capability')
    if supported is not None:need(caps<=set(supported),'renderer capability unsupported')
    used={'core_v1'}
    if o['height']>o['width']:used.add('portrait_v1')
    unique(t['shots'],'shot_id');unique(t['audio_tracks'],'track_id');unique(t['overlays'],'overlay_id');unique(t['subtitles'],'subtitle_id')
    byshot={s['shot_id']:s for s in t['shots']}
    end=0
    for i,s in enumerate(t['shots']):
        a=asset(assets,s['clip_id'],['video'])
        need(s['clip_id'] not in t['excluded_clip_ids'],'excluded clip selected')
        n=s['duration_frames'];overlap=s['transition_in']['duration_frames']
        if s['transition_in']['type']=='dissolve':used.add('dissolve_v1')
        need(i>0 or overlap==0,'first shot cannot dissolve in')
        need(s['start_frame']==end-overlap,'gap or incorrect shot overlap')
        need(overlap<n and (i==0 or overlap<t['shots'][i-1]['duration_frames']),'transition too long')
        next_overlap=t['shots'][i+1]['transition_in']['duration_frames'] if i+1<len(t['shots']) else 0
        need(overlap+next_overlap<n,'triple-overlap or no exclusive shot interval')
        need(abs(s['source_in_seconds']*fps-round(s['source_in_seconds']*fps))<0.0001,'video source not on frame grid')
        need(s['source_in_seconds']+n/fps<=a['duration_seconds']+1e-6,'source range exceeds video')
        end=s['start_frame']+n
    need(end==length,'output duration differs from shot extent')
    p=t['duration_policy']
    if p['mode']=='target':need(abs(length-p['target_seconds']*fps)<=p['tolerance_frames'],'target duration mismatch')
    for aid in t['excluded_clip_ids']:asset(assets,aid,['video'])
    bgms=[x for x in t['audio_tracks'] if x['kind']=='bgm']
    need(len(bgms)==1,'need exactly one BGM')
    need(bgms[0]['start_frame']==0 and bgms[0]['duration_frames']==length,'BGM must cover output')
    bytrack={x['track_id']:x for x in t['audio_tracks']}
    speech=[]
    for track in t['audio_tracks']:
        a=asset(assets,track['asset_id'],['video'] if track['kind']=='source_audio' else ['audio'])
        n=track['duration_frames'];st=track['start_frame'];en=st+n
        need(en<=length,'audio exceeds output')
        need(track['source_in_seconds']+n/fps<=a['duration_seconds']+1e-6,'audio exceeds source')
        need(track['fade_in_frames']+track['fade_out_frames']<=n,'audio fades exceed duration')
        points=track['envelope']
        if points:
            used.add('audio_envelopes_v1')
            need(points[0]['offset_frame']==0 and points[-1]['offset_frame']==n,'envelope needs both boundaries')
            need(all(x['offset_frame']<y['offset_frame'] for x,y in zip(points,points[1:])),'unordered envelope')
        if track['kind']=='source_audio':
            need(track['shot_id'] in byshot,'source audio has no shot')
            shot=byshot[track['shot_id']];i=t['shots'].index(shot)
            need(track['asset_id']==shot['clip_id'] and a['has_audio'],'wrong source audio asset')
            need(shot['start_frame']<=st and en<=shot['start_frame']+shot['duration_frames'],'source audio outside shot')
            expected=shot['source_in_seconds']+(st-shot['start_frame'])/fps
            need(abs(expected-track['source_in_seconds'])<1e-6,'source audio not aligned with picture')
            need(shot['transition_in']['type']=='cut' and (i+1==len(t['shots']) or t['shots'][i+1]['transition_in']['type']=='cut'),'speech shot must use hard cuts')
        else:need(track['shot_id'] is None,'non-source audio cannot bind a shot')
        if track['kind']!='bgm':speech.append((st,en))
    speech.sort()
    need(all(a[1]<=b[0] for a,b in zip(speech,speech[1:])),'speech or narration overlaps')
    for x in t['overlays']:
        need(0<=x['start_frame']<x['end_frame']<=length,'overlay outside output')
        check_rect(x['rect'],o)
        animation=x['animation']
        need(animation['in_frames']+animation['out_frames']<=x['end_frame']-x['start_frame'],'overlay animation too long')
        if animation['type']=='fade':used.add('overlay_fade_v1')
        if x['kind']=='text':asset(assets,x['text_style']['font_asset_id'],['font'])
        else:asset(assets,x['asset_id'],['image'])
    for x in t['subtitles']:
        used.add('subtitles_v1');check_rect(x['rect'],o)
        asset(assets,x['text_style']['font_asset_id'],['font'])
        need(x['source_audio_track_id'] in bytrack,'subtitle audio missing')
        audio=bytrack[x['source_audio_track_id']]
        need(audio['kind']!='bgm','subtitle cannot attach to BGM')
        need(audio['start_frame']<=x['start_frame']<x['end_frame']<=audio['start_frame']+audio['duration_frames'],'subtitle outside voice')
        if transcripts is not None and x['source_sentence_id'] is not None:
            need(x['source_sentence_id'] in transcripts,'subtitle sentence missing')
            sentence=transcripts[x['source_sentence_id']]
            need(sentence['asset_id']==audio['asset_id'],'subtitle source mismatch')
            src_in=audio['source_in_seconds'];src_out=src_in+audio['duration_frames']/fps
            need(src_in<=sentence['in_seconds'] and sentence['out_seconds']<=src_out,'voice truncates sentence')
            expected_start=audio['start_frame']+math.floor((sentence['in_seconds']-src_in)*fps+1e-6)
            expected_end=audio['start_frame']+math.ceil((sentence['out_seconds']-src_in)*fps-1e-6)
            need(expected_start<=x['start_frame']<x['end_frame']<=expected_end,'subtitle outside mapped sentence')
    need(used<=caps,'required capability missing from manifest')

def check_config(doc,assets):
    s=doc['settings'];check_output(s['output']);asset(assets,s['music_asset_id'],['audio'])
    need(not s['subtitles_enabled'] or s['voice_enabled'],'subtitles require enabled voice')
    for aid in s['excluded_clip_ids']:asset(assets,aid,['video'])
    for aid in s['creation_brief']['reference_image_asset_ids']:asset(assets,aid,['image'])

def check_stage(doc,stage,assets):
    """Product phase gates are distinct from schema validity/render capabilities."""
    kind=doc['document_type']
    if kind=='edit_request':
        resolution=doc['resolution']
        if resolution['decision']=='ready':
            allowed={'set_title','set_warmth','remove_clip'}
            if stage in ('V2','V3'):allowed|={'set_mood','set_target_length','set_voice','set_subtitles'}
            if stage=='V3':allowed|={'set_aspect_ratio','set_style'}
            for op in resolution['operations']:
                need(op['type'] in allowed,'operation unavailable in this product phase')
                if op['type']=='set_title':
                    need(len(op['value'])<={'eyebrow':40,'headline':60,'tagline':80}[op['field']],'title exceeds layer limit')
                if op['type']=='remove_clip':asset(assets,op['clip_id'],['video'])
                if op['type']=='set_target_length' and stage!='V3':need(op['seconds']!=60,'60 seconds requires V3')
        elif resolution['decision']=='needs_selection':
            unique(resolution['candidates'],'clip_id')
            for c in resolution['candidates']:asset(assets,c['clip_id'],['video'])
    if kind in ('timeline','project_config'):
        data=doc['timeline'] if kind=='timeline' else doc['settings']
        if stage!='V3':
            need(data['output']['width']==1280 and data['output']['height']==720,'portrait requires V3')
            need(data['duration_policy']['target_seconds']!=60,'60 seconds requires V3')
        if stage=='MVP':
            need(data['duration_policy']['target_seconds'] in (None,30),'MVP has no custom duration')
        if kind=='project_config' and stage=='MVP':
            need(data['style_id']=='magazine_scrapbook' and data['mood_id'] is None,'MVP style/mood gate')
            need(not data['voice_enabled'] and not data['subtitles_enabled'],'MVP voice gate')
        if kind=='project_config' and stage!='V3':
            need(data['creation_brief']=={'text':None,'reference_image_asset_ids':[]},'creation brief requires V3')
        if kind=='timeline':
            if stage=='MVP':
                need(data['required_capabilities']==['core_v1'],'MVP renderer capabilities')
                need(len(data['audio_tracks'])==1 and data['audio_tracks'][0]['kind']=='bgm','MVP BGM only')
                need(not data['subtitles'] and data['style_snapshot']['mood_id'] is None,'MVP feature gate')
            if stage!='V3':
                need(all(x['transition_in']['type']=='cut' for x in data['shots']),'dissolve requires V3')
                need(all(x['role'] not in ('chapter','sticker') and x['animation']['type']=='none' for x in data['overlays']),'overlay feature requires V3')
                need(all(x['kind']!='narration' for x in data['audio_tracks']),'narration requires V3')

def check_transcript(doc,assets):
    unique(doc['sentences'],'sentence_id')
    for sentence in doc['sentences']:
        a=asset(assets,sentence['asset_id'],['video','audio'])
        if a['kind']=='video':need(a['has_audio'],'transcript attached to silent asset')
        need(0<=sentence['in_seconds']<sentence['out_seconds']<=a['duration_seconds'],'invalid sentence range')
        for word in sentence['words']:
            need(sentence['in_seconds']<=word['in_seconds']<word['out_seconds']<=sentence['out_seconds'],'word outside sentence')

def main():
    docs={p.name:json.loads(p.read_text()) for p in (ROOT/'examples').glob('*.json')}
    for d in docs.values():structural(d,SCHEMA)
    assets=check_assets(docs['assets.json'])
    transcripts={s['sentence_id']:s for s in docs['v2.transcript.json']['sentences']}
    for name,d in docs.items():
        kind=d['document_type']
        if kind=='timeline':check_timeline(d,assets,transcripts=transcripts)
        if kind=='edit_plan':check_plan(d,assets)
        if kind=='project_config':check_config(d,assets)
        if kind=='transcript':check_transcript(d,assets)
        stage='V3' if name.startswith('v3.') else 'V2' if name.startswith('v2.') else 'MVP'
        check_stage(d,stage,assets)
    for prefix in ['mvp','mvp.after-delete','v2','v3']:
        c=docs[prefix+'.config.json'];t=docs[prefix+'.timeline.json']
        need(c['version_id']==t['version_id'] and c['parent_version_id']==t['parent_version_id'],'version mismatch')
        for field in ['output','duration_policy','excluded_clip_ids']:
            need(c['settings'][field]==t['timeline'][field],f'config/timeline mismatch: {field}')
        need(c['settings']['music_asset_id']==t['timeline']['audio_tracks'][0]['asset_id'],'music mismatch')
    base=docs['mvp.timeline.json']
    failed=0
    def reject(label,mutate,source=None,supported=None):
        nonlocal failed
        d=deepcopy(source or base);mutate(d)
        try:
            structural(d,SCHEMA);check_timeline(d,assets,supported=supported,transcripts=transcripts)
        except ValueError:
            failed+=1
            return
        raise AssertionError(f'Invalid fixture accepted: {label}')
    reject('source overflow',lambda d:d['timeline']['shots'][0].update(source_in_seconds=7.0))
    reject('unknown asset',lambda d:d['timeline']['shots'][0].update(clip_id='missing'))
    reject('output gap',lambda d:d['timeline']['shots'][1].update(start_frame=91))
    reject('excluded clip',lambda d:d['timeline'].update(excluded_clip_ids=['clip_01']))
    reject('unknown field',lambda d:d['timeline']['shots'][0].update(speed=2))
    reject('duplicate shot',lambda d:d['timeline']['shots'][1].update(shot_id='shot_01'))
    reject('bad BGM duration',lambda d:d['timeline']['audio_tracks'][0].update(duration_frames=899))
    reject('out of canvas',lambda d:d['timeline']['overlays'][0]['rect'].update(x=1200))
    reject('self-parent',lambda d:d.update(parent_version_id=d['version_id']))
    reject('delete keeps target',lambda d:d['timeline'].update(duration_policy=base['timeline']['duration_policy']),docs['mvp.after-delete.timeline.json'])
    reject('bad subtitle',lambda d:d['timeline']['subtitles'][0].update(end_frame=300),docs['v2.timeline.json'])
    reject('voice misalignment',lambda d:d['timeline']['audio_tracks'][1].update(source_in_seconds=2.0),docs['v2.timeline.json'])
    reject('MVP renderer gets V2',lambda d:None,docs['v2.timeline.json'],['core_v1'])
    reject('missing required cap',lambda d:d['timeline'].update(required_capabilities=['core_v1']),docs['v2.timeline.json'])
    reject('wrong dissolve offset',lambda d:d['timeline']['shots'][5].update(start_frame=450),docs['v3.timeline.json'])
    reject('bad envelope order',lambda d:d['timeline']['audio_tracks'][0]['envelope'][1].update(offset_frame=999),docs['v2.timeline.json'])
    reject('unsupported major',lambda d:d.update(schema_version='2.0.0'))
    for label,op in [('unsupported MVP operation',{'type':'set_target_length','seconds':20}),
                     ('headline layer overflow',{'type':'set_title','field':'headline','value':'X'*70})]:
        d=deepcopy(docs['mvp.edit_request.json'])
        d['resolution']['operations']=[op]
        structural(d,SCHEMA)
        try:check_stage(d,'MVP',assets)
        except ValueError:failed+=1
        else:raise AssertionError(f'Invalid edit accepted: {label}')
    check_timeline(base,assets,supported=['core_v1'])
    print(f'PASS: {len(docs)} JSON fixtures; structural keyword checks; references, frames, audio, overlays, subtitles; {failed} negative cases rejected.')
    print('LIMIT: no media files, fonts, API calls, renderer or Replit deployment were exercised; this is not a full JSON Schema conformance suite.')

if __name__=='__main__':main()
