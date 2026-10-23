"""Application adapter registration; traversal/domain code stays source-neutral."""
from dataclasses import dataclass
from typing import Callable
from fastapi import HTTPException
from app.discovery_pemex import PEMEXConcursosAdapter
from app.discovery_cfe import CFEProcurementAdapter

@dataclass(frozen=True)
class SourceDefinition:
    name:str
    base_url:str
    factory:Callable|None
    version:str
    areas:dict
    capabilities:dict
    @property
    def available(self):return self.factory is not None and self.capabilities.get('automation_status','AVAILABLE')=='AVAILABLE'

SOURCES={
 'PEMEX':SourceDefinition('PEMEX Concursos Abiertos','https://www.pemex.com',PEMEXConcursosAdapter,
    PEMEXConcursosAdapter.version,PEMEXConcursosAdapter.areas,PEMEXConcursosAdapter.capabilities()),
 'CFE':SourceDefinition('CFE', 'https://msc.cfe.mx/Aplicaciones/NCFE/Concursos/',CFEProcurementAdapter,
    CFEProcurementAdapter.version,CFEProcurementAdapter.areas,CFEProcurementAdapter.capabilities()),
 'COMPRAS_MX':SourceDefinition('Compras MX','https://comprasmx.buengobierno.gob.mx/sitiopublico/',None,
    'deferred-access-restriction',{'public':{'label':'Procedimientos actuales'}},
    {'public':True,'automation_status':'DEFERRED_SOURCE_AUTOMATION_RESTRICTED','binary_download':False,
     'reason':'SOURCE_ACCESS_RESTRICTION','message':'DEFERRED — SOURCE AUTOMATION RESTRICTED; acceso manual no autoriza adquisición automatizada.'}),
}

def definition(source):
    value=SOURCES.get(source)
    if value is None:raise HTTPException(422,'UNSUPPORTED_DISCOVERY_SOURCE')
    return value

def require_available(source):
    value=definition(source)
    if not value.available:raise HTTPException(409,'DISCOVERY_SOURCE_AUTOMATION_RESTRICTED')
    return value

def adapter_for(source):return require_available(source).factory()
