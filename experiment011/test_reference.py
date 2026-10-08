import copy
import hashlib
import json
import math
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment010'))
from engine import World
from units import Quantity,convert
from reference import Catalog,UnsupportedProperty,build,digest,validate_manifest
from laboratory import Laboratory

ROOT=Path(__file__).resolve().parent

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.ref=self.root/'ref.sqlite'
        self.data=json.loads((ROOT/'dataset.json').read_text());self.info=build(self.ref);self.v=self.info['version'];self.c=Catalog(self.ref)
    def tearDown(self):self.c.close();self.tmp.cleanup()
    def test_every_known_property_traces_to_conditions_uncertainty_and_source(self):
        for p in self.data['properties']:
            r=self.c.record(p['material_id'],p['name'],self.v)
            self.assertEqual(p,r);self.assertIn('pressure_Pa',r['conditions']);self.assertIn('temperature_K',r['conditions'])
            self.assertIn('kind',r['uncertainty'])
            if r['status']!='unknown':
                s=self.c.source(r['source_id'],self.v);self.assertTrue(s['url'].startswith('https://'));self.assertEqual('2026-10-08',s['accessed']);self.assertTrue(s['rights'])
    def test_source_checked_values_and_classification(self):
        self.assertEqual('63.546',self.c.element('Cu',self.v)['standard_atomic_weight']['value'])
        self.assertEqual('0.003',self.c.element('Cu',self.v)['standard_atomic_weight']['uncertainty']['value'])
        self.assertEqual('62.92959772',self.c.isotope('Cu',63,self.v)['relative_atomic_mass']['value'])
        self.assertEqual('0.00000056',self.c.isotope('Cu',63,self.v)['relative_atomic_mass']['uncertainty']['value'])
        self.assertEqual(['1.00784','1.00811'],self.c.element('H',self.v)['standard_atomic_weight']['value'])
        self.assertIsNone(self.c.isotope('H',3,self.v)['mole_fraction']['value'])
        d=self.c.property('copper','density',self.v,target_units='kg/m3');self.assertEqual(Decimal('8960'),Decimal(d['value']))
        self.assertEqual('reference_nominal',d['status']);self.assertEqual(self.info['sha256'],d['dataset_sha256'])
    def test_units_conversion_and_absolute_interval_semantics(self):
        self.assertEqual(Decimal('273.15'),convert(0,'degC','K'))
        self.assertEqual(Decimal('100000'),convert(1,'bar','Pa'))
        self.assertEqual(Decimal('0.2'),convert('0.2','K','degC',uncertainty=True))
        self.assertEqual(Decimal('2'),convert(2,'delta_degC','delta_K'))
        for source,target in [('kg','K'),('K','delta_K'),('J/(mol K)','J/(kg K)'),('g/cm3','ohm m')]:
            with self.assertRaises(ValueError):convert(1,source,target)
        for v in [True,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):convert(v,'kg','g')
        with self.assertRaises(ValueError):convert(1,'imaginary_unit','kg')
    def test_dimensions_of_established_model(self):
        r=self.c.rest_energy((1,'g'),self.v)
        self.assertEqual(Decimal('89875517873681.764'),Decimal(r['value']));self.assertEqual('calculated',r['status'])
        self.assertIn('model_source',r)
        with self.assertRaises(ValueError):self.c.rest_energy((1,'m'),self.v)
        with self.assertRaises(ValueError):(Quantity.of(1,'kg')*Quantity.of(1,'m')).in_unit('J')
        with self.assertRaises(ValueError):Quantity.of(300,'K')
    def test_identity_and_composition(self):
        self.assertEqual(29,self.c.element('Cu',self.v)['atomic_number'])
        self.assertEqual({'Cu':'1'},self.c.composition('copper',self.v)['fractions'])
        self.assertEqual({'H':'0.111894','O':'0.888106'},self.c.composition('water',self.v)['fractions'])
        self.assertEqual('alloy',self.c.material('al6061-t6',self.v)['kind'])
        with self.assertRaises(UnsupportedProperty):self.c.composition('al6061-t6',self.v)
        with self.assertRaises(UnsupportedProperty):self.c.material('copper-OFHC',self.v)
    def test_missing_properties_explicit_unknown_and_rejected(self):
        for material in ['copper','aluminum','water','al6061-t6']:
            self.assertEqual('unknown',self.c.record(material,'electrical_resistivity',self.v)['status'])
            with self.assertRaises(UnsupportedProperty):self.c.property(material,'electrical_resistivity',self.v)
        with self.assertRaises(UnsupportedProperty):self.c.property('copper','chemical_reactivity',self.v)
    def test_conditions_and_no_extrapolation(self):
        for kwargs in [{'temperature':(300,'K')},{'pressure':(1,'bar')},{'phase':'liquid'}]:
            with self.assertRaises(UnsupportedProperty):self.c.property('copper','density',self.v,**kwargs)
        for T in [1,301]:
            with self.assertRaises(UnsupportedProperty):self.c.property('al6061-t6','specific_heat',self.v,temperature=(T,'K'))
        with self.assertRaises(UnsupportedProperty):self.c.property('al6061-t6','specific_heat',self.v)
        with self.assertRaises(UnsupportedProperty):self.c.property('al6061-t6','specific_heat',self.v,temperature=(100,'K'),pressure=(1,'bar'))
        with self.assertRaises(UnsupportedProperty):self.c.property('copper','molar_heat_capacity',self.v,temperature=(1358,'K'))
    def test_shomate_against_independent_source_display_table(self):
        # NIST's rounded display table, not generated from this implementation.
        for T,Cp in [(300,24.49),(400,25.29),(500,25.99),(1000,28.62),(1300,32.18)]:
            r=self.c.property('copper','molar_heat_capacity',self.v,temperature=(T,'K'))
            self.assertLess(abs(float(r['value'])-Cp),0.0051)
            self.assertEqual('approximation',r['status']);self.assertEqual('not_reported',r['uncertainty']['kind'])
    def test_cryo_model_against_decimal_reference_evaluation(self):
        # Independently sum powers using high precision; production uses floating Horner evaluation.
        for name,coeff,fit in [('thermal_conductivity',['0.07918','1.0957','-0.07277','0.08084','0.02803','-0.09464','0.04179','-0.00571','0'],'0.5'),
                              ('specific_heat',['46.6467','-314.292','866.662','-1298.3','1162.27','-637.795','210.351','-38.3094','2.96344'],'5')]:
            from decimal import localcontext
            for T in [4,100,300]:
                with localcontext() as ctx:
                    ctx.prec=60;x=Decimal(T).log10();expected=Decimal(10)**sum(Decimal(a)*(Decimal(1) if i==0 else x**i) for i,a in enumerate(coeff))
                r=self.c.property('al6061-t6',name,self.v,temperature=(T,'K'));self.assertAlmostEqual(float(r['value'])/float(expected),1,places=8)
                self.assertEqual(fit,r['uncertainty']['value']);self.assertEqual('curve_fit_percent',r['uncertainty']['kind'])
    def test_uncertainty_not_shifted_as_absolute_temperature(self):
        r=self.c.property('copper','melting_temperature',self.v,target_units='degC')
        self.assertEqual(Decimal('1084.80'),Decimal(r['value']));self.assertEqual(Decimal('0.2'),Decimal(r['uncertainty']['value']))
        c=self.c.constant('G',self.v);self.assertEqual('standard',c['uncertainty']['kind']);self.assertEqual(Decimal('1.5e-15'),Decimal(c['uncertainty']['value']))
        self.assertEqual('exact_definition',self.c.constant('c',self.v)['status'])
    def test_dataset_version_fingerprint_and_exclusive_builder(self):
        self.assertEqual(digest(self.data),self.c.dataset_hash(self.v))
        with self.assertRaises(FileExistsError):build(self.ref)
        with self.assertRaises(UnsupportedProperty):self.c.dataset_hash('latest')
        alternate=copy.deepcopy(self.data);alternate['version']='test-release-only'
        p=self.root/'v2.json';p.write_text(json.dumps(alternate));ref2=self.root/'v2.sqlite';build(ref2,p);c=Catalog(ref2)
        try:
            self.assertNotEqual(c.dataset_hash('test-release-only'),self.c.dataset_hash(self.v))
            with self.assertRaises(UnsupportedProperty):c.material('copper',self.v)
        finally:c.close()
    def test_reference_read_only_and_tamper_detection(self):
        with self.assertRaises(sqlite3.OperationalError):self.c.db.execute("UPDATE property SET status='unknown'")
        writer=sqlite3.connect(self.ref);writer.execute("UPDATE property SET units='kg' WHERE name='density'");writer.commit();writer.close()
        with self.assertRaises(ValueError):Catalog(self.ref)
        with self.assertRaises(ValueError):self.c.property('copper','density',self.v)
    def test_import_rejects_bad_source_dimensions_composition_and_model(self):
        changes=[lambda d:d['sources'][0].update(url=''),lambda d:d['properties'][0].update(units='kg'),
                 lambda d:d['materials'][0]['composition'].update(fractions={'Cu':'0.9'}),
                 lambda d:d['materials'][0]['composition'].update(fractions={'Unobtainium':'1'}),
                 lambda d:d['properties'][4]['model'].update(kind='ai-guessed'),
                 lambda d:d['isotopes'][0]['mole_fraction'].update(value='1.2')]
        for change in changes:
            d=copy.deepcopy(self.data);change(d)
            with self.assertRaises(ValueError):validate_manifest(d)
    def test_curated_manifest_reproduces_exactly(self):
        from make_dataset import D
        self.assertEqual(self.data,D)
    def test_experiment010_sources_are_exact_upstream_blobs(self):
        for name,sha in json.loads((ROOT/'baseline_blobs.json').read_text()).items():
            b=(ROOT.parent/'experiment010'/name).read_bytes()
            self.assertEqual(sha,hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest())

class LaboratoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.ref=self.root/'ref.sqlite';self.v=build(self.ref)['version'];self.c=Catalog(self.ref)
        self.wp=self.root/'world.sqlite';self.lp=self.root/'lab.sqlite';self.w=World(self.wp);self.w.explore(0);self.lab=Laboratory(self.lp,self.w,self.c)
        self.lab.create_object('a',0,'copper',self.v,(1,'kg'));self.lab.create_object('b',0,'copper',self.v,(0,'g'))
    def tearDown(self):self.lab.close();self.w.close();self.c.close();self.tmp.cleanup()
    def test_persistent_references_resolve_with_pinned_version(self):
        before=self.lab.state();self.assertEqual(self.v,before['a']['dataset_version']);self.assertEqual(self.c.dataset_hash(self.v),before['a']['dataset_sha256'])
        self.lab.close();self.w.close();self.c.close();self.c=Catalog(self.ref);self.w=World(self.wp);self.lab=Laboratory(self.lp,self.w,self.c)
        self.assertEqual(before,self.lab.state());self.assertEqual('8.96000',self.lab.property('a','density')['value'])
        self.assertTrue(self.lab.verify()['verified']);self.assertTrue(self.w.verify()['verified'])
    def test_invalid_references_and_identity_are_not_created(self):
        before=self.lab.state();events=self.lab.events()
        for args in [('bad',1,'copper',self.v,(1,'kg')),('bad',0,'unknown',self.v,(1,'kg')),('bad',0,'copper','latest',(1,'kg')),('bad',0,'copper',self.v,(-1,'kg'))]:
            with self.assertRaises(ValueError):self.lab.create_object(*args)
            self.assertEqual(before,self.lab.state());self.assertEqual(events,self.lab.events())
        with self.assertRaises(ValueError):Laboratory(self.ref,self.w,self.c)
        with self.assertRaises(ValueError):Laboratory(self.wp,self.w,self.c)
    def test_mass_transfer_conserves_material_and_isolates_world_reference(self):
        refhash=hashlib.sha256(self.ref.read_bytes()).hexdigest();world=self.w.state();events=self.w.events()
        for i in range(10):self.assertTrue(self.lab.commit_transfer(self.lab.propose_transfer('a','b',(1,'g')))['accepted'])
        s=self.lab.state();self.assertEqual(Decimal(1),sum(Decimal(o['mass_kg']) for o in s.values()))
        self.assertEqual(Decimal('0.01'),Decimal(s['b']['mass_kg']));self.assertEqual(world,self.w.state());self.assertEqual(events,self.w.events())
        self.assertEqual(refhash,hashlib.sha256(self.ref.read_bytes()).hexdigest())
        p=self.w.propose('erosion',[0]);self.w.submit('e','test',p);self.w.commit('e')
        self.assertEqual(s,self.lab.state());self.assertEqual(refhash,hashlib.sha256(self.ref.read_bytes()).hexdigest());self.assertTrue(self.lab.verify()['verified'])
    def test_rejected_stale_excess_malformed_mixed_transfers(self):
        self.lab.create_object('al',0,'aluminum',self.v,(1,'kg'))
        proposals=[None,{},self.lab.propose_transfer('a','b',(2,'kg')),self.lab.propose_transfer('a','al',(1,'g'))]
        p=self.lab.propose_transfer('a','b',(1,'g'));p['versions']['a']=-1;proposals.append(p)
        p=self.lab.propose_transfer('a','b',(1,'g'));p['mass_kg']='NaN';proposals.append(p)
        before=self.lab.state();events=self.lab.events()
        for proposal in proposals:
            self.assertFalse(self.lab.commit_transfer(proposal)['accepted']);self.assertEqual(before,self.lab.state());self.assertEqual(events,self.lab.events())
    def test_transaction_failure_rolls_back_both_objects_and_event(self):
        before=self.lab.state();events=self.lab.events();p=self.lab.propose_transfer('a','b',(1,'g'))
        self.lab.db.execute("CREATE TRIGGER fail_lab BEFORE INSERT ON lab_events BEGIN SELECT RAISE(ABORT,'fault'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.lab.commit_transfer(p)
        self.assertEqual(before,self.lab.state());self.assertEqual(events,self.lab.events())
    def test_subprocess_crash_recovery_before_and_after_commit(self):
        prefix="import sys; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent/'experiment010')); from engine import World; from reference import Catalog; from laboratory import Laboratory; import os; w=World(sys.argv[1]); c=Catalog(sys.argv[2]); lab=Laboratory(sys.argv[3],w,c); "
        args=[str(self.wp),str(self.ref),str(self.lp)]
        crash=prefix+"lab.db.execute('BEGIN IMMEDIATE'); lab.db.execute('DELETE FROM objects'); os._exit(9)"
        self.assertEqual(9,subprocess.run([sys.executable,'-c',crash,*args],cwd=ROOT).returncode)
        self.lab.close();self.lab=Laboratory(self.lp,self.w,self.c);self.assertEqual(2,len(self.lab.state()))
        commit=prefix+"assert lab.commit_transfer(lab.propose_transfer('a','b',(1,'g')))['accepted']; os._exit(8)"
        self.assertEqual(8,subprocess.run([sys.executable,'-c',commit,*args],cwd=ROOT).returncode)
        self.lab.close();self.lab=Laboratory(self.lp,self.w,self.c);self.assertEqual(Decimal('0.001'),Decimal(self.lab.state()['b']['mass_kg']))
        self.assertTrue(self.lab.verify()['verified'])
    def test_pinned_dataset_mismatch_fails_closed(self):
        d=json.loads((ROOT/'dataset.json').read_text());d['constants'][0]['value']='299792457' # adversarial fixture, never a released reference value
        path=self.root/'tampered.json';path.write_text(json.dumps(d));newref=self.root/'tampered.sqlite';build(newref,path);other=Catalog(newref)
        try:
            with self.assertRaises(ValueError):Laboratory(self.lp,self.w,other)
        finally:other.close()
    def test_lab_rejects_other_world_and_audit_tampering(self):
        other=World(self.root/'other.sqlite');other.explore(0)
        try:
            with self.assertRaises(ValueError):Laboratory(self.lp,other,self.c)
        finally:other.close()
        with self.assertRaises(sqlite3.IntegrityError):self.lab.db.execute('DELETE FROM lab_events')
        self.lab.db.execute("UPDATE objects SET record='{}' WHERE id='a'")
        with self.assertRaises(ValueError):self.lab.verify()
    def test_two_clients_revalidate_current_lab_versions(self):
        second=Laboratory(self.lp,self.w,self.c)
        try:
            p=second.propose_transfer('a','b',(1,'g'))
            self.assertTrue(self.lab.commit_transfer(self.lab.propose_transfer('a','b',(2,'g')))['accepted'])
            before=self.lab.state();events=self.lab.events()
            self.assertFalse(second.commit_transfer(p)['accepted']);self.assertEqual(before,self.lab.state());self.assertEqual(events,self.lab.events())
        finally:second.close()
    def test_decimal_ledger_range_and_resolution(self):
        for mass in [('1e13','kg'),('1e-10','kg')]:
            with self.assertRaises(ValueError):self.lab.create_object('bad',0,'copper',self.v,mass)

if __name__=='__main__':unittest.main(verbosity=2)
