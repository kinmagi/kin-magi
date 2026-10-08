"""Small typed adapters for official endpoints; unsupported records stay out of releases."""
import hashlib,json,os,re
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlencode
from compat import number
from transport import AccessUnavailable
NIST_URL='https://physics.nist.gov/cuu/Constants/Table/allascii.txt'
NIST_RIGHTS='https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications'
PUBCHEM_ROOT='https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/'
MP_ROOT='https://api.materialsproject.org/materials/summary/'
POLICIES={
 'nist':{'interval':1.0,'rights_url':NIST_RIGHTS,'license':'NIST SRD 121; attribution and current NIST terms required'},
 'pubchem':{'interval':1.0,'rights_url':'https://pubchem.ncbi.nlm.nih.gov/docs/downloads','license':'Contributor-dependent; NCBI policy is not a universal data licence'},
 'materials_project':{'interval':1.0,'rights_url':'https://materialsproject.org/about/terms','license':'Materials Project terms; explicit local terms acceptance required'}}

def allowed_url(source,url):
    if source=='nist':return url==NIST_URL
    if source=='pubchem':return bool(re.fullmatch(re.escape(PUBCHEM_ROOT)+r'[1-9][0-9]*/property/MolecularFormula,MolecularWeight/JSON',url))
    if source=='materials_project':
        p=urlsplit(url)
        return p.scheme=='https' and p.netloc=='api.materialsproject.org' and p.path=='/materials/summary/' and not p.fragment
    return False

def provenance(source,evidence,version,reference,license_status):
    return {'source':source,'url':evidence['url'],'retrieved_at':evidence['retrieved_at'],
            'raw_sha256':evidence['sha256'],'capture':evidence['mode'],'source_version':version,
            'publication_reference':reference,'license':POLICIES[source]['license'],
            'rights_url':POLICIES[source]['rights_url'],'license_status':license_status}

def record(source,key,subject,prop,value,units,kind,conditions,uncertainty,evidence,version,reference,license_status):
    return {'schema':1,'key':key,'subject':subject,'property':prop,'value':value,'units':units,
            'kind':kind,'conditions':conditions,'uncertainty':uncertainty,
            'provenance':provenance(source,evidence,version,reference,license_status)}

class NIST:
    name='nist'
    # Only explicit finite supported constants. Ellipsis-valued expansions are rejected.
    selected={'electron mass':('electron_mass','kg'),'atomic mass constant':('m_u','kg')}
    def fetch(self,transport,query=None,refresh=False):
        body,headers,evidence=transport.get(self.name,NIST_URL,refresh=refresh)
        return self.parse(body,evidence)
    def parse(self,body,evidence):
        text=body.decode('utf-8');version=re.search(r'(\d{4}) CODATA adjustment',text)
        if not version:raise ValueError('CODATA release missing')
        results=[]
        for label,(key,expected) in self.selected.items():
            matches=[s for s in text.splitlines() if s[:60].strip()==label]
            if len(matches)!=1:raise ValueError('selected constant missing or duplicated: '+label)
            line=matches[0];value=line[60:85].replace(' ','').strip();unc=line[85:110].replace(' ','').strip();units=line[110:].strip()
            if units!=expected:raise ValueError('unexpected CODATA unit')
            value=str(number(value));u='0' if unc=='(exact)' else str(number(unc))
            results.append(record(self.name,'constant:'+key,{'type':'constant','id':key},key,value,units,
                'exact' if unc=='(exact)' else 'measured',{'scope':'CODATA recommended fundamental constant; no ambient-condition model'},
                {'value':u,'units':units,'kind':'exact' if unc=='(exact)' else 'standard','note':'CODATA recommended uncertainty'},
                evidence,version[1],'CODATA recommended values '+version[1]+'; NIST SRD 121','review_required'))
        return results

class PubChem:
    name='pubchem'
    def fetch(self,transport,query,refresh=False):
        cid=query.get('cid')
        if type(cid)!=int or not 1<=cid<=1_000_000_000:raise ValueError('explicit positive CID required')
        url=PUBCHEM_ROOT+str(cid)+'/property/MolecularFormula,MolecularWeight/JSON'
        body,headers,evidence=transport.get(self.name,url,refresh=refresh)
        return self.parse(body,evidence,cid)
    def parse(self,body,evidence,cid):
        rows=json.loads(body)['PropertyTable']['Properties']
        if len(rows)!=1 or rows[0]['CID']!=cid:raise ValueError('PubChem identity mismatch')
        row=rows[0]
        # Molecular weight is a computed descriptor, not a measured bulk-material density.
        return [record(self.name,'pubchem:'+str(cid)+':molecular_weight',{'type':'compound','namespace':'PubChem CID','id':str(cid),'formula':row['MolecularFormula']},
            'molecular_weight',str(number(row['MolecularWeight'])),'g/mol','calculated',
            {'scope':'PubChem computed molecular descriptor; no bulk phase or ambient conditions'},
            {'value':None,'units':'g/mol','kind':'unknown','note':'Endpoint does not report measurement uncertainty'},
            evidence,'snapshot:'+evidence['sha256'],'PubChem CID '+str(cid)+'; PUG REST computed properties; publication not supplied','unresolved')]

class MaterialsProject:
    name='materials_project'
    def fetch(self,transport,query,refresh=False):
        key=os.getenv('MP_API_KEY')
        if not key:raise AccessUnavailable('MP_API_KEY required; no request made')
        if query.get('terms_accepted') is not True:raise AccessUnavailable('review and accept current Materials Project terms first')
        mid=query.get('material_id','')
        if not re.fullmatch(r'mp-[1-9][0-9]*',mid):raise ValueError('Materials Project identity required')
        url=MP_ROOT+'?'+urlencode({'material_ids':mid,'_fields':'material_id,formula_pretty,density,origins,last_updated','_limit':1})
        body,headers,evidence=transport.get(self.name,url,headers={'X-API-KEY':key},refresh=refresh)
        return self.parse(body,evidence,mid)
    def parse(self,body,evidence,mid):
        result=json.loads(body);rows=result['data']
        if len(rows)!=1 or rows[0]['material_id']!=mid:raise ValueError('Materials Project identity mismatch')
        row=rows[0];version=result.get('meta',{}).get('db_version') or row.get('last_updated')
        if not version:raise ValueError('source version missing')
        return [record(self.name,'mp:'+mid+':density',{'type':'crystal','namespace':'Materials Project','id':mid,'formula':row['formula_pretty']},
            'density',None if row.get('density') is None else str(number(row['density'])),'g/cm3',
            'unknown' if row.get('density') is None else 'calculated',
            {'temperature_K':None,'pressure_Pa':None,'phase':'computed crystal','scope':'Relaxed computed structure; no experimental T/P validity supplied'},
            {'value':None,'units':'g/cm3','kind':'unknown','note':'Summary API reports no measurement uncertainty'},
            evidence,str(version),'Materials Project task origins: '+json.dumps(row.get('origins',[]),sort_keys=True),'review_required')]

CONNECTORS={c.name:c() for c in (NIST,PubChem,MaterialsProject)}
