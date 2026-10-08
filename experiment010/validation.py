"""Independent authority relative to proposal producers, using registered models."""
import math
from models import MODELS, TOL, inventories, valid_state

def close(a,b):
    if isinstance(a,dict):
        return isinstance(b,dict) and set(a)==set(b) and all(close(v,b[k]) for k,v in a.items())
    if type(a) is int: return type(b) is int and a==b
    return type(b) in (int,float) and math.isfinite(b) and abs(a-b)<=TOL

def validate(before, operation, proposed):
    try:
        for s in before.values(): valid_state(s)
        expected=MODELS[operation].solve(before)
        if not isinstance(proposed,dict) or set(proposed)!=set(before):
            raise ValueError('target/schema mismatch')
        for s in proposed.values(): valid_state(s)
        if not close(expected,proposed): raise ValueError('proposal conflicts with registered model')
        old,new=inventories(before),inventories(proposed)
        if any(abs(old[k]-new[k])>TOL for k in old): raise ValueError('conservation violation')
        for k,s in proposed.items():
            for other,t in proposed.items():
                if int(other)==int(k)+1 and s['right_boundary_mm']!=t['left_boundary_mm']:
                    raise ValueError('discontinuous shared boundary')
        return {'accepted':True,'reasons':[]},expected
    except (ValueError,TypeError,KeyError,OverflowError) as e:
        return {'accepted':False,'reasons':[str(e)]},None
