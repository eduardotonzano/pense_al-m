from dataclasses import dataclass

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
