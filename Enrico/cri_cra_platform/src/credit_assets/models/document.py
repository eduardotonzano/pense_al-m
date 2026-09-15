from dataclasses import dataclass

@dataclass(frozen=True)
class Document:
    source_document_id: str
    category: str
    document_name: str
    source: str
    source_url: str
    reference_date: str = ""
    publication_date: str = ""
    file_hash: str = ""
