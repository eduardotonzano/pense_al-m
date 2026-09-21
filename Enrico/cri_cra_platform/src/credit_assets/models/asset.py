from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Asset:
    codigo_cetip: str
    tipo_ativo: str
    securitizadora: str
    cnpj_securitizadora: str
    emissao: str
    serie: str
    devedor: str = ""
    cnpj_devedor: str = ""
    isin: str = ""
    asset_id: Optional[int] = None
