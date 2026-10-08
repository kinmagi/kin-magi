"""Curated transcription script. Every scientific numeral below was source-checked.
Not an AI value generator or network importer. Writes the versioned JSON manifest.
"""
import json
from pathlib import Path

RIGHTS='https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications'
D={'schema_version':1,'version':'cw011-2026-10-08.1','sources':[], 'elements':[], 'isotopes':[], 'materials':[], 'properties':[], 'constants':[]}

def source(id,title,url,release,rights='NIST non-SRD attribution; see DATA_NOTICES.md',reference=None):
    D['sources'].append({'id':id,'title':title,'url':url,'accessed':'2026-10-08','release':release,
                         'rights':rights,'rights_url':RIGHTS,'reference':reference,
                         'verification':'Checked against the linked primary-source page via browser on access date; not a raw page snapshot.'})

for symbol in ('H','O','Al','Cu'):
    source('isotopes-'+symbol,'NIST Atomic Weights and Isotopic Compositions: '+symbol,
           'https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele='+symbol,
           'NIST compilation last data update January 2015; atomic weights 2013, isotopic composition 2009, AME2012',
           reference='Coursey, Schwab, Tsai and Dragoset; Meija et al. (2013 weights), Berglund and Wieser (2009 compositions), Wang et al. (AME2012)')
source('isotope-notes','NIST isotopic column descriptions','https://physics.nist.gov/PhysRefData/Compositions/notes.html','source page')
source('atomic-index','NIST atomic dataset scope and provenance','https://www.nist.gov/pml/atomic-weights-and-isotopic-compositions-relative-atomic-masses','2015 data; page updated 2024')
for id,num,title in [('copper',29,'COPPER'),('aluminum',13,'ALUMINUM'),('water',276,'WATER, LIQUID')]:
    source('star-'+id,'NIST STAR composition of '+title,
           'https://physics.nist.gov/cgi-bin/Star/compos.pl?matno='+str(num).zfill(3),'page snapshot access date')
source('density-notes','NIST X-ray nominal density context','https://physics.nist.gov/PhysRefData/XrayMassCoef/tab1.html','source page; nominal evaluation constants')
source('cu-cp','NIST Chemistry WebBook SRD 69: copper solid Shomate heat capacity',
       'https://webbook.nist.gov/cgi/cbook.cgi?ID=C7440508&Mask=2','2025 WebBook data release; coefficients Chase 1998; reviewed June 1977',
       'SRD 69 compilation copyright US Secretary of Commerce; limited scientific factual excerpt, not full-database redistribution; see DATA_NOTICES.md',
       'Chase, M.W., Jr., NIST-JANAF Thermochemical Tables, Fourth Edition, J. Phys. Chem. Ref. Data, Monograph 9 (1998), 1-1951; DOI for WebBook: 10.18434/T4D303')
source('cu-melting','NIST Chemistry WebBook SRD 69: copper fusion temperature',
       'https://webbook.nist.gov/cgi/cbook.cgi?ID=C7440508&Mask=4','2025 WebBook data release; Anonymous 1988',
       'SRD 69 compilation copyright US Secretary of Commerce; limited scientific factual excerpt; see DATA_NOTICES.md',
       'Anonymous, NBS Spec. Publ. (U.S.) 260 (1988), as cited by NIST TRC; TRC-assigned uncertainty')
source('al6061','NIST cryogenic material properties: 6061-T6 Aluminum UNS A96061',
       'https://trc.nist.gov/cryogenics/materials/6061%20Aluminum/6061_T6Aluminum_rev.htm','no release identifier displayed; access date pin',
       reference='NIST cryogenic compilation; property-specific bibliography in cryo-refs')
source('cryo-refs','NIST cryogenic material properties bibliography, Aluminum 6061 section',
       'https://trc.nist.gov/cryogenics/materials/references.htm','source page',
       reference='Specific heat: LNG Materials and Fluids, Douglas Mann (ed.), NBS Cryogenics Division, 1977. Conductivity: Thermal Properties Database for Materials at Cryogenic Temperatures, Holly M. Veres (ed.), Vol. 1; Touloukian, Purdue University, February 1965, as listed by NIST.')
source('codata','NIST 2022 CODATA fundamental constants',
       'https://physics.nist.gov/cuu/Constants/Table/allascii.txt','2022 CODATA adjustment')

source('rest-energy-model',"NIST Kilogram: Mass and Planck's Constant (mass-energy relation)",
       'https://www.nist.gov/si-redefinition/kilogram/kilogram-mass-and-plancks-constant','source page; established relation E=m*c^2')
source('si-conversions','NIST SP 811 Appendix B.8: conversion factors',
       'https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8','SP 811 unit definitions/conversion factors')
source('si-units','NIST SP 811 Chapter 4: SI units and prefixes',
       'https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes','SP 811 dimensional and Celsius definitions; not used for historical pre-2019 constant values')

def uncertainty(value=None,kind='not_reported',note='Source does not report a measurement uncertainty for this item.'):
    return {'value':value,'kind':kind,'note':note}

def fact(value,units='1',unc=None,conditions=None):
    return {'value':value,'units':units,'uncertainty':unc or uncertainty(),
            'conditions':conditions or {'scope':'normal terrestrial material; representative compilation, not a specimen measurement'}}

for sym,name,z,weight,unc in [('H','hydrogen',1,['1.00784','1.00811'],None),('O','oxygen',8,['15.99903','15.99977'],None),
                             ('Al','aluminum',13,'26.9815385','0.0000007'),('Cu','copper',29,'63.546','0.003')]:
    w=fact(weight,unc=uncertainty(unc,'source_parenthetical','Source parenthetical uncertainty; not assumed to be a one-sigma standard uncertainty.') if unc else
           uncertainty(None,'natural_variation_interval','The value is a published interval of standard atomic weights, not a point estimate or confidence interval.'))
    D['elements'].append({'symbol':sym,'name':name,'atomic_number':z,'source_id':'isotopes-'+sym,
                         'standard_atomic_weight':w,'status':'reference_compilation','notes':'Relative atomic weight is dimensionless; no scalar is substituted for an interval.'})

rows=[('H',1,'1.00782503223','0.00000000009','0.999885','0.000070'),
      ('H',2,'2.01410177812','0.00000000012','0.000115','0.000070'),
      ('H',3,'3.0160492779','0.0000000024',None,None),
      ('O',16,'15.99491461957','0.00000000017','0.99757','0.00016'),
      ('O',17,'16.99913175650','0.00000000069','0.00038','0.00001'),
      ('O',18,'17.99915961286','0.00000000076','0.00205','0.00014'),
      ('Al',27,'26.98153853','0.00000011','1',None),
      ('Cu',63,'62.92959772','0.00000056','0.6915','0.0015'),
      ('Cu',65,'64.92778970','0.00000071','0.3085','0.0015')]
for sym,a,m,mu,x,xu in rows:
    D['isotopes'].append({'element_symbol':sym,'mass_number':a,'source_id':'isotopes-'+sym,
       'relative_atomic_mass':fact(m,unc=uncertainty(mu,'source_parenthetical','Source parenthetical uncertainty, not presumed Gaussian.')),
       'mole_fraction':fact(x,unc=uncertainty(xu,'source_parenthetical' if xu else 'not_reported',
           'Representative abundance variation and experimental error; no covariance supplied. Tritium abundance is not tabulated.' if x is None else
           'Representative composition, not a universal specimen composition.'))})

for id,name,kind,composition,source_id,phase,identifier in [
 ('copper','Copper','metal',{'Cu':'1'},'star-copper','solid','element Cu; not OFHC or a certified batch'),
 ('aluminum','Aluminum','metal',{'Al':'1'},'star-aluminum','solid','element Al; not alloy 6061'),
 ('water','Liquid water, NIST STAR nominal composition','compound',{'H':'0.111894','O':'0.888106'},'star-water','liquid','STAR material 276'),
 ('al6061-t6','6061-T6 aluminum','alloy',None,'al6061','solid','UNS A96061; temper T6')]:
    D['materials'].append({'id':id,'name':name,'kind':kind,'phase':phase,'source_id':source_id,'identifier':identifier,
        'composition':{'basis':'mass_fraction' if composition else 'unknown','fractions':composition,
                       'units':'1','source_id':source_id,'uncertainty':uncertainty(),
                       'conditions':{'scope':'NIST nominal elemental composition' if composition else 'Grade and temper identity only; no certified batch composition on selected NIST page'},
                       'status':'reference_nominal' if composition else 'unknown'}})

PUNITS={'density':'g/cm3','thermal_conductivity':'W/(m K)','electrical_resistivity':'ohm m',
        'specific_heat':'J/(kg K)','melting_temperature':'K','molar_heat_capacity':'J/(mol K)'}
def prop(material,name,status,source_id,value=None,conditions=None,unc=None,model=None,note=None):
    D['properties'].append({'material_id':material,'name':name,'status':status,'source_id':source_id,'units':PUNITS[name],
                            'value':value,'conditions':conditions or {'temperature_K':None,'pressure_Pa':None,'phase':None},
                            'uncertainty':unc or uncertainty(),'model':model,'note':note})
for material,v in [('copper','8.96000'),('aluminum','2.69890'),('water','1.00000')]:
    prop(material,'density','reference_nominal','star-'+material,v,
         {'temperature_K':None,'pressure_Pa':None,'phase':'liquid' if material=='water' else 'solid'},
         note='Nominal material constant for NIST radiation/stopping-power evaluation; temperature and pressure not supplied. Not a condition-calibrated density measurement.')
prop('copper','melting_temperature','reference_nominal','cu-melting','1357.95',
     {'temperature_K':None,'pressure_Pa':None,'phase':'solid-liquid transition'},
     uncertainty('0.2','TRC_assigned','TRC assigned 0.2 K; coverage factor not specified.'),note='Nominal catalog value, not reclassified as a direct verified measurement.')
prop('copper','molar_heat_capacity','approximation','cu-cp',
     conditions={'temperature_K':[298,1358],'pressure_Pa':None,'phase':'solid','scope':'standard-state Cp; pressure-specific queries unsupported'},
     model={'kind':'shomate_cp','coefficients':['17.72891','28.09870','-31.25289','13.97243','0.068611'],
            'formula':'Cp/(J mol^-1 K^-1) = A + B*t + C*t^2 + D*t^3 + E/t^2; t=T/(1000 K)',
            'implementation_max_K':1357,'limit_note':'Conservative 1357 K cap below nominal 1357.95 K fusion point; no metastable solid extrapolation.'},
     note='Calculated from a source-published approximation; coefficient and fit uncertainties not reported.')
for name,coef,error in [('thermal_conductivity',['0.07918','1.0957','-0.07277','0.08084','0.02803','-0.09464','0.04179','-0.00571','0'],'0.5'),
                        ('specific_heat',['46.6467','-314.292','866.662','-1298.3','1162.27','-637.795','210.351','-38.3094','2.96344'],'5')]:
    prop('al6061-t6',name,'approximation','al6061',conditions={'temperature_K':[4,300],'pressure_Pa':None,'phase':'solid','scope':'6061-T6 only; pressure and batch composition unspecified'},
         unc=uncertainty(error,'curve_fit_percent','Percent error relative to source data; not a full measurement uncertainty or confidence bound.'),
         model={'kind':'log10_polynomial','coefficients':coef,'formula':'log10(y / output_unit) = sum(a_i * log10(T/(1 K))^i)',
                'source_equation_min_K':1 if name=='thermal_conductivity' else 4,'source_data_min_K':4},
         note='Evaluation restricted to overlap of source data and equation ranges (4–300 K). No extrapolation to 1 K.')
for material in D['materials']:
    for name in PUNITS:
        if not any(p['material_id']==material['id'] and p['name']==name for p in D['properties']):
            prop(material['id'],name,'unknown',None,note='No verified applicable value curated in this release. This does not assert that the property is absent from scientific literature.')
for id,name,v,u,unc,scope in [
 ('c','speed of light in vacuum','299792458','m/s','0','vacuum'),
 ('k_B','Boltzmann constant','1.380649e-23','J/K','0','SI defining constant'),
 ('N_A','Avogadro constant','6.02214076e23','1/mol','0','SI defining constant'),
 ('G','Newtonian constant of gravitation','6.67430e-11','m3/(kg s2)','0.00015e-11','CODATA 2022 adjustment'),
 ('m_u','atomic mass constant','1.66053906892e-27','kg','0.00000000052e-27','CODATA 2022 adjustment')]:
    D['constants'].append({'id':id,'name':name,'source_id':'codata','value':v,'units':u,'status':'exact_definition' if unc=='0' else 'reference_measurement',
        'conditions':{'scope':scope,'temperature_K':None,'pressure_Pa':None},
        'uncertainty':uncertainty(unc,'exact' if unc=='0' else 'standard','Zero for SI defining values; CODATA standard uncertainty for adjusted constants.')})

def annotate_uncertainty_units(value):
    if isinstance(value,dict):
        if 'uncertainty' in value and 'units' in value:
            value['uncertainty']['units']='percent' if value['uncertainty']['kind']=='curve_fit_percent' else value['units']
        for child in value.values():annotate_uncertainty_units(child)
    elif isinstance(value,list):
        for child in value:annotate_uncertainty_units(child)

annotate_uncertainty_units(D)

if __name__=='__main__':
    target=Path(__file__).with_name('dataset.json')
    target.write_text(json.dumps(D,indent=2,ensure_ascii=False)+'\n')
