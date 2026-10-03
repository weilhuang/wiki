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
before = m.snapshot()
result = m.cancel('alice','red','o1','c1',1,mode='async',fault='after-order')
check('async-abort-result',result,'STORAGE_ABORT')
check('async-abort-full-state',m.snapshot(),before)
print(json.dumps({'status':'PASS'}))
