from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any

@dataclass(slots=True)
class SourcedValue:
    value: Any = None
    source: str = "indisponivel"
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def available(self) -> bool:
        return self.value is not None

@dataclass(slots=True)
class Issuer:
    name: SourcedValue = field(default_factory=SourcedValue)
    cnpj: SourcedValue = field(default_factory=SourcedValue)

@dataclass(slots=True)
class MarketPriceSnapshot:
    price: SourcedValue = field(default_factory=SourcedValue)
    rate: SourcedValue = field(default_factory=SourcedValue)
    reference_date: SourcedValue = field(default_factory=SourcedValue)

@dataclass(slots=True)
class Event:
    event_type: str
    date: str | None = None
    source: str = "indisponivel"

@dataclass(slots=True)
class Document:
    title: str
    url: str
    source: str = "indisponivel"

@dataclass(slots=True)
class ManualInput:
    rating: Any = None
    rate: Any = None
    outstanding_quantity: Any = None

@dataclass(slots=True)
class Debenture:
    asset_code: SourcedValue = field(default_factory=SourcedValue)
    isin: SourcedValue = field(default_factory=SourcedValue)
    issuer: Issuer = field(default_factory=Issuer)
    indexer: SourcedValue = field(default_factory=SourcedValue)
    spread: SourcedValue = field(default_factory=SourcedValue)
    guarantee: SourcedValue = field(default_factory=SourcedValue)
    asset_class: SourcedValue = field(default_factory=SourcedValue)
    issued_quantity: SourcedValue = field(default_factory=SourcedValue)
    outstanding_quantity: SourcedValue = field(default_factory=SourcedValue)
    nominal_value: SourcedValue = field(default_factory=SourcedValue)
    trustee: SourcedValue = field(default_factory=SourcedValue)
    status: SourcedValue = field(default_factory=SourcedValue)
    rating: SourcedValue = field(default_factory=SourcedValue)
    market: list[MarketPriceSnapshot] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)

    def merge_from(self, incoming: "Debenture") -> None:
        for f in fields(self):
            current = getattr(self, f.name)
            new = getattr(incoming, f.name)
            if isinstance(current, SourcedValue) and isinstance(new, SourcedValue):
                if new.available:
                    setattr(self, f.name, new)
            elif isinstance(current, Issuer) and isinstance(new, Issuer):
                if new.name.available: current.name = new.name
                if new.cnpj.available: current.cnpj = new.cnpj
            elif isinstance(current, list) and new:
                current.extend(new)
