"""Versioned, offline reference catalog. Builder is separate from read-only lookup."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Protocol
from decimal import Decimal
import math
from units import Quantity, convert, number, unit

PROPERTY_UNITS={'density':'g/cm3','thermal_conductivity':'W/(m K)','electrical_resistivity':'ohm m',
                'specific_heat':'J/(kg K)','melting_temperature':'K','molar_heat_capacity':'J/(mol K)'}
STATUSES={'reference_measurement','reference_nominal','approximation','unknown'}

class UnsupportedProperty(ValueError):pass

class ReferenceProvider(Protocol):
    def material(self,material_id: str,version: str) -> dict: ...
    def dataset_hash(self,version: str) -> str: ...
    def property(self,material_id: str,name: str,version: str,**conditions) -> dict: ...


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

def require(test,message):
    if not test:raise ValueError(message)

def numeric_fact(f):
    unit(f['units'])
    value=f['value']
    if isinstance(value,list):
        require(len(value)==2 and number(value[0])<=number(value[1]),'invalid interval')
    elif value is not None:number(value)
    u=f['uncertainty'];require(isinstance(u['kind'],str) and bool(u['note']),'uncertainty metadata required')
    if u['value'] is not None:require(number(u['value'])>=0,'negative uncertainty')
    require(isinstance(f['conditions'],dict) and bool(f['conditions']),'conditions required')


def validate_manifest(data):
    require(data['schema_version']==1 and isinstance(data['version'],str) and data['version'],'unsupported dataset version')
    canonical(data)  # Reject NaN, infinity and values that cannot be stored as JSON.
    sources={s['id']:s for s in data['sources']}
    require(len(sources)==len(data['sources']),'duplicate source')
    for s in sources.values():
        require(s['url'].startswith('https://') and s['accessed'] and s['title'] and s['rights'] and s['release'],'source traceability missing')
    def sourced(item):require(item['source_id'] in sources,'unknown scientific source')
    elements={e['symbol']:e for e in data['elements']}
    require(len(elements)==len(data['elements']),'duplicate element')
    numbers=[]
    for e in elements.values():
        sourced(e);z=e['atomic_number'];require(type(z) is int and 1<=z<=118,'invalid atomic number');numbers.append(z)
        numeric_fact(e['standard_atomic_weight']);require(e['standard_atomic_weight']['units']=='1','relative weight must be dimensionless')
    require(len(set(numbers))==len(numbers),'duplicate atomic number')
    isotope_ids=set();fractions={}
    for i in data['isotopes']:
        sourced(i);sym=i['element_symbol'];a=i['mass_number'];require(sym in elements and type(a) is int and a>=elements[sym]['atomic_number'],'invalid isotope identity')
        key=(sym,a);require(key not in isotope_ids,'duplicate isotope');isotope_ids.add(key)
        for field in ['relative_atomic_mass','mole_fraction']:numeric_fact(i[field]);require(i[field]['units']=='1','relative isotope fields must be dimensionless')
        require(number(i['relative_atomic_mass']['value'])>0,'invalid isotope mass')
        x=i['mole_fraction']['value']
        if x is not None:
            require(0<=number(x)<=1,'invalid isotope abundance');fractions.setdefault(sym,[]).append(number(x))
    for values in fractions.values():require(abs(sum(values)-1)<=Decimal('0.000001'),'representative isotope fractions do not sum to one')
    materials={m['id']:m for m in data['materials']};require(len(materials)==len(data['materials']),'duplicate material')
    for m in materials.values():
        sourced(m);require(m['kind'] in {'metal','alloy','compound','other'},'invalid material kind')
        require(m['phase'] in {'solid','liquid','gas'} and bool(m['identifier']),'material identity incomplete')
        c=m['composition'];sourced(c);require(c['units']=='1' and bool(c['conditions']) and bool(c['uncertainty']),'composition metadata missing')
        if c['basis']=='unknown':require(c['fractions'] is None and c['status']=='unknown','unknown composition must not invent fractions')
        else:
            require(c['basis'] in {'mass_fraction','mole_fraction'},'unsupported composition basis')
            require(isinstance(c['fractions'],dict) and bool(c['fractions']),'composition missing')
            require(all(k in elements and 0<number(v)<=1 for k,v in c['fractions'].items()),'invalid composition identity/fraction')
            require(abs(sum(number(v) for v in c['fractions'].values())-1)<=Decimal('1e-9'),'composition does not sum to one')
    seen=set()
    for p in data['properties']:
        key=(p['material_id'],p['name']);require(key not in seen and key[0] in materials,'duplicate/unknown property target');seen.add(key)
        require(p['name'] in PROPERTY_UNITS,'unimplemented property dimension')
        require(unit(p['units'])[0]==unit(PROPERTY_UNITS[p['name']])[0],'property dimension mismatch')
        require(p['status'] in STATUSES,'invalid scientific classification');numeric_fact(p)
        c=p['conditions']
        require(set(c)>={'temperature_K','pressure_Pa','phase'},'condition metadata incomplete')
        for axis in ('temperature_K','pressure_Pa'):
            value=c[axis]
            if isinstance(value,list):require(len(value)==2 and 0<number(value[0])<=number(value[1]),'invalid condition interval')
            elif value is not None:require(number(value)>0,'invalid condition value')
        if p['status']=='unknown':
            require(p['value'] is None and p['model'] is None and p['source_id'] is None and p['note'],'unknown property has invented data')
        else:
            sourced(p)
            if p['status']=='approximation':
                require(p['value'] is None and isinstance(p['model'],dict),'fit metadata missing')
                model=p['model'];coeff=model['coefficients'];require(isinstance(c['temperature_K'],list),'fit requires temperature limits')
                for a in coeff:number(a)
                if model['kind']=='shomate_cp':
                    require(p['name']=='molar_heat_capacity' and p['units']=='J/(mol K)' and len(coeff)==5,'Shomate dimensions/schema invalid')
                    require(c['temperature_K'][0]<=model['implementation_max_K']<=c['temperature_K'][1],'invalid phase cap')
                elif model['kind']=='log10_polynomial':
                    require(p['name'] in {'specific_heat','thermal_conductivity'} and len(coeff)==9,'unsupported log fit')
                    require(p['units']==PROPERTY_UNITS[p['name']],'fit output unit must equal the source unit')
                else:raise ValueError('unregistered scientific model')
            else:require(p['model'] is None and p['value'] is not None and number(p['value'])>0,'scalar reference value missing')
    require(seen=={(m,n) for m in materials for n in PROPERTY_UNITS},'coverage must explicitly label missing properties')
    constants=set()
    for c in data['constants']:
        sourced(c);numeric_fact(c);require(c['id'] not in constants,'duplicate constant');constants.add(c['id'])
        require(c['status'] in {'exact_definition','reference_measurement'},'invalid constant classification')
        require(number(c['value'])>0,'invalid constant value')
        if c['status']=='exact_definition':require(c['uncertainty']['kind']=='exact' and number(c['uncertainty']['value'])==0,'exact definition needs zero uncertainty')
    return data


def rows(data):
    v=data['version']
    return {
      'source':[(v,s['id'],s['title'],s['url'],s['accessed'],s['rights'],canonical(s)) for s in data['sources']],
      'element':[(v,e['symbol'],e['atomic_number'],e['source_id'],canonical(e)) for e in data['elements']],
      'isotope':[(v,i['element_symbol'],i['mass_number'],i['source_id'],canonical(i)) for i in data['isotopes']],
      'material':[(v,m['id'],m['kind'],m['source_id'],canonical(m)) for m in data['materials']],
      'property':[(v,p['material_id'],p['name'],p['status'],p['units'],p['source_id'],canonical(p['conditions']),canonical(p['uncertainty']),canonical(p)) for p in data['properties']],
      'constant':[(v,c['id'],c['source_id'],c['units'],canonical(c)) for c in data['constants']]}


def build(path,manifest_path=None):
    """Build one immutable release, exclusively into a NEW file; never migrate in place."""
    data=validate_manifest(json.loads(Path(manifest_path or Path(__file__).with_name('dataset.json')).read_text()))
    path=Path(path).resolve()
    with path.open('xb'):pass
    db=None
    try:
        db=sqlite3.connect(path)
        db.executescript(Path(__file__).with_name('schema.sql').read_text())
        with db:
            db.execute('INSERT INTO dataset VALUES (?,?,?)',(data['version'],digest(data),canonical(data)))
            for table,items in rows(data).items():
                if items:db.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in items[0])+')',items)
        db.close();db=None
    except BaseException:
        if db is not None:db.close()
        path.unlink(missing_ok=True);raise
    return {'version':data['version'],'sha256':digest(data)}

class Catalog:
    """Lookup only. Reference data is never a laboratory write target."""
    def __init__(self,path):
        self.path=Path(path).resolve()
        self.db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        self.db.execute('PRAGMA query_only=ON')
        try:self.verify()
        except BaseException:self.db.close();raise

    def close(self):self.db.close()
    def versions(self):return [r[0] for r in self.db.execute('SELECT version FROM dataset ORDER BY version')]
    def dataset_hash(self,version):
        self.verify()
        row=self.db.execute('SELECT sha256 FROM dataset WHERE version=?',(version,)).fetchone()
        if row is None:raise UnsupportedProperty('dataset version unavailable')
        return row[0]
    def verify(self):
        require(self.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','reference database corrupt')
        require(not self.db.execute('PRAGMA foreign_key_check').fetchall(),'reference foreign key violation')
        manifests=self.db.execute('SELECT * FROM dataset').fetchall();require(bool(manifests),'empty catalog')
        expected={t:[] for t in ['source','element','isotope','material','property','constant']}
        for version,sha,raw in manifests:
            data=validate_manifest(json.loads(raw));require(data['version']==version and digest(data)==sha,'dataset fingerprint mismatch')
            for table,items in rows(data).items():expected[table].extend(items)
        for table,items in expected.items():
            actual=self.db.execute('SELECT * FROM '+table).fetchall()
            require(sorted(actual,key=repr)==sorted(items,key=repr),'normalized reference rows differ from version manifest: '+table)
        return True
    def _lookup(self,table,where,args):
        self.verify()  # Detect accidental edits by an external writer before resolving data.
        row=self.db.execute('SELECT record FROM '+table+' WHERE '+where,args).fetchone()
        if row is None:raise UnsupportedProperty('reference identity/property unavailable')
        return json.loads(row[0])
    def source(self,id,version):return self._lookup('source','id=? AND dataset_version=?',(id,version))
    def element(self,symbol,version):return self._lookup('element','symbol=? AND dataset_version=?',(symbol,version))
    def isotope(self,symbol,mass_number,version):return self._lookup('isotope','element_symbol=? AND mass_number=? AND dataset_version=?',(symbol,mass_number,version))
    def material(self,id,version):return self._lookup('material','id=? AND dataset_version=?',(id,version))
    def composition(self,id,version):
        value=self.material(id,version)['composition']
        if value['status']=='unknown':raise UnsupportedProperty('material composition unknown; no batch certificate curated')
        return value
    def record(self,id,name,version):
        self.material(id,version)
        return self._lookup('property','material_id=? AND name=? AND dataset_version=?',(id,name,version))
    def constant(self,id,version,target_units=None):
        c=self._lookup('constant','id=? AND dataset_version=?',(id,version));return self._result(c,version,target_units,'reference')
    def _result(self,record,version,target_units,evaluation):
        result=dict(record);source_units=record['units'];target=target_units or source_units
        result['value']=str(convert(record['value'],source_units,target))
        result['units']=target;result['dataset_version']=version;result['dataset_sha256']=self.dataset_hash(version)
        result['source']=self.source(record['source_id'],version);result['evaluation']=evaluation
        result['uncertainty']=dict(record['uncertainty'])
        if record['uncertainty']['kind']!='curve_fit_percent':result['uncertainty']['units']=target
        if record['uncertainty']['value'] is not None and record['uncertainty']['kind']!='curve_fit_percent':
            result['uncertainty']['value']=str(convert(record['uncertainty']['value'],source_units,target,uncertainty=True))
        return result
    def property(self,id,name,version,*,temperature=None,pressure=None,phase=None,target_units=None):
        """Conditions are (value, units) pairs. Never interpolate/extrapolate unspecified axes."""
        p=self.record(id,name,version)
        if p['status']=='unknown':raise UnsupportedProperty(p['note'])
        c=p['conditions']
        if phase is not None and phase!=c['phase']:raise UnsupportedProperty('phase mismatch')
        supplied={}
        for key,q,target in [('temperature_K',temperature,'K'),('pressure_Pa',pressure,'Pa')]:
            if q is None:continue
            if not isinstance(q,(tuple,list)) or len(q)!=2:raise ValueError('condition must be a (value, units) pair')
            x=convert(q[0],q[1],target);require(x>0,'condition must be positive in SI')
            limits=c[key]
            if limits is None:raise UnsupportedProperty('source does not specify requested '+key)
            if isinstance(limits,list):
                if not number(limits[0])<=x<=number(limits[1]):raise UnsupportedProperty('condition outside source validity range')
            elif x!=number(limits):raise UnsupportedProperty('condition differs from reference measurement')
            supplied[key]=x
        if p['status']=='approximation':
            if 'temperature_K' not in supplied:raise UnsupportedProperty('temperature required for source fit')
            T=supplied['temperature_K'];m=p['model'];co=[number(v) for v in m['coefficients']]
            if m['kind']=='shomate_cp':
                if T>number(m['implementation_max_K']):raise UnsupportedProperty('outside conservative solid-phase limit')
                t=T/1000;A,B,C,D,E=co;y=A+B*t+C*t*t+D*t*t*t+E/(t*t)
            else:
                # Logs take dimensionless T/(1 K); output is in source-specified units.
                x=math.log10(float(T));acc=0.0
                for a in reversed(co):acc=acc*x+float(a)
                y=number(10**acc)
            require(y>0,'invalid source model evaluation')
            p=dict(p,value=str(y))
            p['evaluated_conditions']={k:str(v) for k,v in supplied.items()}
            return self._result(p,version,target_units,'calculated_from_source_approximation')
        return self._result(p,version,target_units,'reference')
    def rest_energy(self,mass,version):
        """E=m c² for supplied rest mass; pure query, not a world energy change."""
        m=Quantity.of(mass[0],mass[1]);require(m.dimensions==unit('kg')[0] and m.value>=0,'rest mass must be nonnegative mass')
        c=self.constant('c',version);q=Quantity.of(c['value'],c['units']);E=(m*q*q).in_unit('J')
        return {'value':str(E),'units':'J','status':'calculated','model':'rest_energy_v1: E=m*c^2',
                'conditions':{'scope':'rest energy; not kinetic energy or available chemical energy'},
                'uncertainty':{'value':None,'units':'J','kind':'not_reported','note':'No input mass uncertainty supplied; c is exact.'},
                'source':c['source'],'model_source':self.source('rest-energy-model',version),'dataset_version':version,'dataset_sha256':self.dataset_hash(version)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--manifest');a=p.parse_args()
    print(json.dumps(build(a.out,a.manifest),indent=2))
