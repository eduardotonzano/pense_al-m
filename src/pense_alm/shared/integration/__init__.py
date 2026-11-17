"""Integracoes graduais com modulos legados."""

from .batch_import_error import BatchImportError
from .batch_import_report import BatchImportReport
from .debenture_instrument_adapter import (
    DebentureInstrumentAdapter,
)
from .debenture_instrument_batch_import_service import (
    DebentureInstrumentBatchImportService,
    InstrumentBatchOutcome,
)
from .debenture_instrument_import_service import (
    DebentureInstrumentImportService,
)
from .debenture_issuer_adapter import (
    DebentureIssuerAdapter,
)
from .debenture_issuer_batch_import_service import (
    DebentureIssuerBatchImportService,
)
from .debenture_issuer_import_service import (
    DebentureIssuerImportService,
)
from .fundos_adapter import (
    FundosAdapter,
    FundosAdapterError,
    FundosReason,
    NameResolution,
    SituationGroup,
    TypeResolution,
)
from .fundos_import_report import (
    FundosBacklog,
    FundosEntityReport,
    FundosImportError,
    FundosNaoCriados,
    PrestadorasNaoCriadas,
)
from .fundos_import_service import (
    FundosEntityPhase,
    FundosImportService,
)
from .fundos_reader import (
    CadastroNotFound,
    FundosDatabaseReader,
    FundosDatabaseUnavailable,
    FundosReaderError,
    FundosSchemaError,
    build_read_only_uri,
)
from .fundos_records import (
    CadastroSnapshot,
    FundosPartyLink,
    FundosSubjectRecord,
)
from .import_result import (
    EntityImportAction,
    EntityImportResult,
    InstrumentImportReason,
    InstrumentImportResult,
)
from .legacy_datetime import parse_legacy_datetime
from .legacy_instrument_reader import (
    LegacyDebentureInstrumentReader,
    LegacyInstrumentReadError,
)
from .legacy_issuer_reader import (
    LegacyDebentureIssuerReader,
)
from .records import (
    DebentureInstrumentRecord,
    DebentureIssuerRecord,
)

__all__ = [
    "BatchImportError",
    "BatchImportReport",
    "CadastroNotFound",
    "CadastroSnapshot",
    "DebentureInstrumentAdapter",
    "DebentureInstrumentBatchImportService",
    "DebentureInstrumentImportService",
    "DebentureInstrumentRecord",
    "DebentureIssuerAdapter",
    "DebentureIssuerBatchImportService",
    "DebentureIssuerImportService",
    "DebentureIssuerRecord",
    "EntityImportAction",
    "EntityImportResult",
    "FundosAdapter",
    "FundosAdapterError",
    "FundosBacklog",
    "FundosDatabaseReader",
    "FundosDatabaseUnavailable",
    "FundosEntityPhase",
    "FundosEntityReport",
    "FundosImportError",
    "FundosImportService",
    "FundosNaoCriados",
    "FundosPartyLink",
    "FundosReaderError",
    "FundosReason",
    "FundosSchemaError",
    "FundosSubjectRecord",
    "InstrumentBatchOutcome",
    "InstrumentImportReason",
    "InstrumentImportResult",
    "LegacyDebentureInstrumentReader",
    "LegacyDebentureIssuerReader",
    "LegacyInstrumentReadError",
    "NameResolution",
    "PrestadorasNaoCriadas",
    "SituationGroup",
    "TypeResolution",
    "build_read_only_uri",
    "parse_legacy_datetime",
]
