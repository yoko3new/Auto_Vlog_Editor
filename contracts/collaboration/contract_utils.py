"""Small checker for this kit's used schema subset, not an OpenAPI validator.

Use a standard JSON Schema/OpenAPI tool in the application. This helper makes
the development fixtures and stdlib mock usable without installing packages.
It deliberately does not implement all JSON Schema keywords or format checks.
"""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = json.loads((ROOT / 'api.openapi.json').read_text())
EXAMPLES = json.loads((ROOT / 'api.examples.json').read_text())['examples']


def check(value, schema, path='$'):
    def need(test, reason):
        if not test:
            raise ValueError(f'{path}: {reason}')
    if '$ref' in schema:
        target=SPEC
        for key in schema['$ref'].removeprefix('#/').split('/'):
            target=target[key]
        return check(value, target, path)
    for key in ('oneOf','anyOf'):
        if key in schema:
            hits=0
            for child in schema[key]:
                try:
                    check(value,child,path);hits+=1
                except ValueError:
                    pass
            need(hits==1 if key=='oneOf' else hits>0, f'{key} matched {hits} alternatives')
    if 'const' in schema:
        need(type(value) is type(schema['const']) and value==schema['const'],'wrong constant')
    if 'enum' in schema:
        need(any(type(value) is type(x) and value==x for x in schema['enum']),'invalid enum')
    types={'object': isinstance(value,dict), 'array':isinstance(value,list),
           'string':isinstance(value,str), 'number':type(value) in (int,float),
           'integer':type(value) is int, 'boolean':type(value) is bool,'null':value is None}
    if 'type' in schema: need(types[schema['type']], 'wrong type')
    if isinstance(value,dict):
        props=schema.get('properties',{})
        need(set(schema.get('required',[])) <= value.keys(),'missing fields')
        if schema.get('additionalProperties') is False: need(value.keys() <= props.keys(),'unknown fields')
        for k,v in value.items():
            if k in props: check(v,props[k],path+'.'+k)
    if isinstance(value,list):
        need(len(value)>=schema.get('minItems',0),'array too short')
        if schema.get('uniqueItems'): need(len({json.dumps(x,sort_keys=True) for x in value})==len(value),'duplicate items')
        if 'items' in schema:
            for i,v in enumerate(value):check(v,schema['items'],f'{path}[{i}]')
    if isinstance(value,str):
        need(schema.get('minLength',0)<=len(value)<=schema.get('maxLength',math.inf),'string length')
        if 'pattern' in schema:need(re.search(schema['pattern'],value) is not None,'pattern')
    if type(value) in (int,float):
        need(math.isfinite(value),'non-finite number')
        need(schema.get('minimum',-math.inf)<=value<=schema.get('maximum',math.inf),'numeric range')


def validate(value, name):
    check(value, SPEC['components']['schemas'][name])
