from dataclasses import dataclass
from typing import Optional


DOCUMENT_CATEGORIES = (
    "Termo de Securitização",
    "Aditamento",
    "Informe Mensal",
    "Ata/Edital",
    "Fato Relevante",
    "Relatório Agente Fiduciário",
    "Relatório de Rating",
    "Anúncio de Encerramento",
    "Outro",
)


@dataclass(frozen=True)
class Document:
    asset_id: int
    source_document_id: str
    category: str
    document_name: str
    source: str
    source_url: str
    reference_date: Optional[str] = None
    publication_date: Optional[str] = None
    file_hash: Optional[str] = None
    download_status: str = "pending"
    run_id: Optional[str] = None
    collected_at: Optional[str] = None
