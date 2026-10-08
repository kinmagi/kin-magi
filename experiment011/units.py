"""Small explicit SI registry. Unknown units and dimension changes fail closed."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# SI exponents: mass, length, time, temperature, amount, current.
UNITS = {
    '1': ((0,0,0,0,0,0),'1','0','linear'),
    'kg': ((1,0,0,0,0,0),'1','0','linear'),
    'g': ((1,0,0,0,0,0),'0.001','0','linear'),
    'm': ((0,1,0,0,0,0),'1','0','linear'),
    's': ((0,0,1,0,0,0),'1','0','linear'),
    'mol': ((0,0,0,0,1,0),'1','0','linear'),
    'K': ((0,0,0,1,0,0),'1','0','absolute'),
    'degC': ((0,0,0,1,0,0),'1','273.15','absolute'),
    'delta_K': ((0,0,0,1,0,0),'1','0','interval'),
    'delta_degC': ((0,0,0,1,0,0),'1','0','interval'),
    'Pa': ((1,-1,-2,0,0,0),'1','0','linear'),
    'bar': ((1,-1,-2,0,0,0),'100000','0','linear'),
    'kPa': ((1,-1,-2,0,0,0),'1000','0','linear'),
    'kg/m3': ((1,-3,0,0,0,0),'1','0','linear'),
    'g/cm3': ((1,-3,0,0,0,0),'1000','0','linear'),
    'W/(m K)': ((1,1,-3,-1,0,0),'1','0','linear'),
    'ohm m': ((1,3,-3,0,0,-2),'1','0','linear'),
    'J/(kg K)': ((0,2,-2,-1,0,0),'1','0','linear'),
    'J/(mol K)': ((1,2,-2,-1,-1,0),'1','0','linear'),
    'J/K': ((1,2,-2,-1,0,0),'1','0','linear'),
    'J': ((1,2,-2,0,0,0),'1','0','linear'),
    'kJ': ((1,2,-2,0,0,0),'1000','0','linear'),
    'm/s': ((0,1,-1,0,0,0),'1','0','linear'),
    '1/mol': ((0,0,0,0,-1,0),'1','0','linear'),
    'm3/(kg s2)': ((-1,3,-2,0,0,0),'1','0','linear'),
}

def number(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float,Decimal)):
        raise ValueError('finite number required')
    try: result=Decimal(str(value))
    except InvalidOperation as exc: raise ValueError('finite number required') from exc
    if not result.is_finite(): raise ValueError('finite number required')
    return result

def unit(name):
    try:return UNITS[name]
    except (KeyError,TypeError) as exc:raise ValueError('unsupported unit') from exc

def convert(value, source, target, *, uncertainty=False):
    a,b=unit(source),unit(target)
    if a[0]!=b[0] or a[3]!=b[3]: raise ValueError('incompatible dimensions or temperature semantics')
    x=number(value)
    if uncertainty:
        if x<0:raise ValueError('negative uncertainty')
        return x*Decimal(a[1])/Decimal(b[1])
    base=x*Decimal(a[1])+Decimal(a[2])
    if a[3]=='absolute' and base<0:raise ValueError('negative absolute temperature')
    return (base-Decimal(b[2]))/Decimal(b[1])

@dataclass(frozen=True)
class Quantity:
    value: Decimal
    dimensions: tuple

    @classmethod
    def of(cls,value,name):
        u=unit(name)
        if u[3]=='absolute':raise ValueError('absolute temperatures cannot be multiplied')
        return cls(number(value)*Decimal(u[1]),u[0])

    def __mul__(self,other):
        return Quantity(self.value*other.value,tuple(a+b for a,b in zip(self.dimensions,other.dimensions)))

    def in_unit(self,name):
        u=unit(name)
        if u[0]!=self.dimensions or u[3]=='absolute':raise ValueError('incompatible result dimensions')
        return self.value/Decimal(u[1])
