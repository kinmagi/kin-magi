"""Versioned, deliberately restricted scientific models; no AI dependencies."""
import copy
import math
from typing import Protocol

MODEL_VERSION = '010.1'
TOL = 1e-6

class Model(Protocol):
    def solve(self, states: dict) -> dict: ...


def substrate(index):
    if type(index) is not int or abs(index) > 1_000_000:
        raise ValueError('region index must be an integer in [-1000000,1000000]')
    return {'version': 0, 'index': index,
            'left_boundary_mm': 10000 + 200 * index,
            'right_boundary_mm': 10000 + 200 * (index + 1),
            'shore_tonnes': 100.0, 'offshore_tonnes': 0.0,
            'volumes_m3': {'A': 50000.0, 'B': 60000.0}}


def valid_state(s):
    template = substrate(s['index'])
    if set(s) != set(template) or type(s['version']) is not int or s['version'] < 0:
        raise ValueError('invalid state schema/version')
    for k in ('left_boundary_mm', 'right_boundary_mm'):
        if type(s[k]) is not int or s[k] != template[k]:
            raise ValueError('boundary conflicts with canonical substrate')
    if not isinstance(s['volumes_m3'], dict) or set(s['volumes_m3']) != {'A','B'}:
        raise ValueError('invalid reservoirs')
    for x in [s['shore_tonnes'],s['offshore_tonnes'],*s['volumes_m3'].values()]:
        if type(x) not in (int,float) or not math.isfinite(x) or x < 0:
            raise ValueError('nonfinite, negative or nonnumeric inventory')


def inventories(states):
    return {'water_m3': math.fsum(v for s in states.values() for v in s['volumes_m3'].values()),
            'sediment_tonnes': math.fsum(s['shore_tonnes']+s['offshore_tonnes'] for s in states.values())}

class Equalization:
    """Ideal equilibrium, fixed equal beds (100m); areas A=10000,B=20000 m²."""
    def solve(self, states):
        if len(states) != 1: raise ValueError('equalization requires one region')
        result = copy.deepcopy(states)
        for s in result.values():
            total = math.fsum(s['volumes_m3'].values())
            a = total / 3.0
            s['volumes_m3'] = {'A': a, 'B': total - a}
            s['version'] += 1
        return result

class Erosion:
    """Illustrative one-step transfer of up to 2 tonnes to a local offshore store."""
    def solve(self, states):
        if len(states) != 1: raise ValueError('erosion requires one region')
        result = copy.deepcopy(states)
        for s in result.values():
            loss = min(2.0,s['shore_tonnes'])
            s['shore_tonnes'] -= loss; s['offshore_tonnes'] += loss; s['version'] += 1
        return result

class BoundaryTransfer:
    """Illustrative transfer of up to 1 tonne offshore sediment left to right."""
    def solve(self, states):
        keys=sorted(states,key=int)
        if len(keys)!=2 or int(keys[1]) != int(keys[0])+1:
            raise ValueError('transfer requires two adjacent regions')
        result=copy.deepcopy(states);left,right=(result[k] for k in keys)
        amount=min(1.0,left['offshore_tonnes'])
        left['offshore_tonnes']-=amount;right['offshore_tonnes']+=amount
        left['version']+=1;right['version']+=1
        return result

MODELS = {'equalization': Equalization(), 'erosion': Erosion(), 'boundary_transfer': BoundaryTransfer()}
