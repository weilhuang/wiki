"""Independent minimal probe; pass the directory containing review_model.py."""
import importlib.util
import json
import sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('subject',Path(sys.argv[1])/'review_model.py')
subject=importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
ReviewModel=subject.ReviewModel
def check(code,actual,expected):
    if actual != expected:
        print(json.dumps({'status':'FAIL','code':code,'actual':actual,'expected':expected},sort_keys=True))
        raise SystemExit(1)
m = ReviewModel()
check('fixture-pending',m.cancel('alice','red','o1','c1',1,mode='async'),'PENDING')
event = 'red/o1/cancel/2'
check('fixture-release',m.release(event,7),'RELEASED')
check('fixture-confirm',m.confirm(event),'CANCELLED')
check('fixture-final',m.state['orders']['red/o1']['status'],'CANCELLED')
check('fixture-responsibility-remains',m.state['outbox'],{event:{'key':'red/o1','version':2,'operation':'red/alice/c1'}})
check('completed-outbox-rejects-v1',m.rollback_allowed(),False)
print(json.dumps({'status':'PASS'}))
