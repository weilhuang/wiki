"""Small Go 1.27 JSON lifecycle/semantic gate, adapted from the reviewed P2 parser.

Names are explicitly declared; slashes in one t.Run leaf do not invent parents.
"""
import json
import re


def events(raw):
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    if not rows or any(not isinstance(e, dict) for e in rows):
        raise ValueError('missing or invalid Go events')
    return rows


def lifecycle(raw, expected, terminal='pass'):
    rows = events(raw)
    if set(e.get('Package') for e in rows) != set(expected):
        raise ValueError('exact package inventory differs')
    for package, names in expected.items():
        names = set(names)
        own = [e for e in rows if e.get('Package') == package]
        if any(e.get('Action') not in ('start', 'run', 'output', terminal) for e in own):
            raise ValueError('unexpected action, skip or failure')
        if any((e['Action']=='start' and e.get('Test')) or (e['Action']=='run' and not e.get('Test')) for e in own):
            raise ValueError('invalid lifecycle attribution')
        starts = [e for e in own if e['Action']=='start' and not e.get('Test')]
        ends = [e for e in own if e['Action']==terminal and not e.get('Test')]
        if len(starts)!=1 or len(ends)!=1 or own[0] is not starts[0] or own[-1] is not ends[0]:
            raise ValueError('package start/terminal count or order differs')
        if {e['Test'] for e in own if e.get('Test')} != names:
            raise ValueError('exact test run inventory differs')
        bounds = {}
        for name in names:
            selected = [(i,e) for i,e in enumerate(own) if e.get('Test')==name]
            runs = [i for i,e in selected if e['Action']=='run']
            terms = [i for i,e in selected if e['Action']==terminal]
            if len(runs)!=1 or len(terms)!=1 or selected[0][0]!=runs[0] or selected[-1][0]!=terms[0]:
                raise ValueError('test run/terminal count or order differs')
            bounds[name] = (runs[0], terms[0])
        for child in names:
            # Only parents actually present in the declared Go test inventory exist.
            for parent in names:
                if child.startswith(parent+'/') and not (bounds[parent][0] < bounds[child][0] < bounds[child][1] < bounds[parent][1]):
                    raise ValueError('declared parent lifecycle does not contain child')
    return rows


def positive(raw, expected, frames_only=False):
    rows = lifecycle(raw, expected)
    for event in rows:
        if event['Action'] != 'output': continue
        if not isinstance(event.get('Output'), str): raise ValueError('invalid output payload')
        if event.get('OutputType') not in (None, 'frame'): raise ValueError('error output in positive trace')
        for line in event['Output'].splitlines():
            text = line.strip(); name = event.get('Test'); package = event['Package']
            if re.search(r'(?i)(?:^panic:|^fatal error:|test timed out|\[build failed\]|\[setup failed\]|^--- FAIL:|^FAIL(?:\s|$)|SEMANTIC_ASSERT)', text):
                raise ValueError('failure output in positive trace')
            if not frames_only: continue
            if name:
                if event.get('OutputType')!='frame' or not re.fullmatch(r'(?:=== (?:RUN|NAME)\s+'+re.escape(name)+r'|--- PASS: '+re.escape(name)+r' \([0-9]+(?:\.[0-9]+)?s\))', text):
                    raise ValueError('unclassified baseline test output')
            elif text=='PASS':
                if event.get('OutputType')!='frame': raise ValueError('unclassified baseline package frame')
            elif event.get('OutputType') is not None or not re.fullmatch(r'ok\s+'+re.escape(package)+r'\s+[0-9]+(?:\.[0-9]+)?s', text):
                raise ValueError('unclassified baseline package output')
    return [{'package':package,'test':name,'status':'pass'} for package,names in sorted(expected.items()) for name in sorted(names)]


def semantic(raw, code, package, names, leaf, marker):
    if type(code) is not int or code != 1: raise ValueError('semantic rejection requires exit1')
    rows = lifecycle(raw, {package:names}, terminal='fail')
    assertions = []
    for event in rows:
        if event['Action']!='output': continue
        if not isinstance(event.get('Output'),str): raise ValueError('invalid output payload')
        name = event.get('Test')
        for line in event['Output'].splitlines():
            text = line.strip()
            if name:
                frame = re.fullmatch(r'(?:=== (?:RUN|NAME)\s+'+re.escape(name)+r'|--- FAIL: '+re.escape(name)+r' \([0-9]+(?:\.[0-9]+)?s\))',text)
                if frame:
                    if event.get('OutputType')!='frame': raise ValueError('framework output lacks frame attribution')
                    continue
                if name != leaf: raise ValueError('unclassified parent assertion or output')
                match = re.fullmatch(r'[A-Za-z0-9_./-]+\.go:[0-9]+: SEMANTIC_ASSERT (.+)',text)
                if not match or event.get('OutputType')!='error':
                    raise ValueError('unclassified leaf assertion, cleanup, panic, or setup output')
                record = json.loads(match.group(1))
                if (set(record)!={'marker','got','want'} or not all(isinstance(v,str) for v in record.values())
                        or record['marker']!=marker or record['got']==record['want']):
                    raise ValueError('wrong structured semantic assertion')
                assertions.append(record)
            elif event.get('OutputType')!='frame' or not (text=='FAIL' or re.fullmatch(r'FAIL\s+'+re.escape(package)+r'\s+[0-9]+(?:\.[0-9]+)?s',text)):
                raise ValueError('unclassified package output')
    if len(assertions)!=1: raise ValueError('unique semantic assertion count differs')
    return {'test':leaf,'assertion':marker,'exit_code':code,'package':package,'run_names':names,'semantic_assertion':assertions[0]}
