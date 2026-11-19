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
from .fundos_cadastro_import import (
    FundosCadastroImport,
    FundosCadastroRun,
    SnapshotOlderThanApplied,
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
from .fundos_investment_rules import (
    HolderPairs,
    HolderReading,
    InvestmentDecision,
    InvestmentPair,
    InvestmentSkip,
    SkippedInvestment,
    classify_investments,
    collect_investment_pairs,
    investment_to_save,
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
    CadastroIncompleteReason,
    CadastroSnapshot,
    CdaHoldingLink,
    FundosPartyLink,
    FundosSubjectRecord,
)
from .fundos_relation_report import (
    FundosRelationError,
    FundosRelationReport,
    RelacoesNaoCriadas,
    RelacoesPorTipo,
)
from .fundos_relation_rules import (
    FundPairs,
    PairSkip,
    RelationDecision,
    RelationOperation,
    RelationOutcome,
    RelationPair,
    SkippedPair,
    absent_outcome,
    classify,
    collect_pairs,
    decision_is_coherent,
    fund_side,
    operation_for,
    present_outcome,
    relationship_to_save,
    unresolved_pair_types,
)
from .fundos_relation_service import (
    FundosRelationService,
)
from .fundos_target_state import (
    FundosTargetState,
    FundosTargetStateError,
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
    "CadastroIncompleteReason",
    "CadastroNotFound",
    "CadastroSnapshot",
    "CdaHoldingLink",
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
    "FundPairs",
    "FundosAdapter",
    "FundosAdapterError",
    "FundosBacklog",
    "FundosCadastroImport",
    "FundosCadastroRun",
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
    "FundosRelationError",
    "FundosRelationReport",
    "FundosRelationService",
    "FundosSchemaError",
    "FundosSubjectRecord",
    "FundosTargetState",
    "FundosTargetStateError",
    "HolderPairs",
    "HolderReading",
    "InstrumentBatchOutcome",
    "InstrumentImportReason",
    "InstrumentImportResult",
    "InvestmentDecision",
    "InvestmentPair",
    "InvestmentSkip",
    "LegacyDebentureInstrumentReader",
    "LegacyDebentureIssuerReader",
    "LegacyInstrumentReadError",
    "NameResolution",
    "PairSkip",
    "PrestadorasNaoCriadas",
    "RelacoesNaoCriadas",
    "RelacoesPorTipo",
    "RelationDecision",
    "RelationOperation",
    "RelationOutcome",
    "RelationPair",
    "SituationGroup",
    "SkippedInvestment",
    "SkippedPair",
    "SnapshotOlderThanApplied",
    "TypeResolution",
    "absent_outcome",
    "build_read_only_uri",
    "classify",
    "classify_investments",
    "collect_investment_pairs",
    "collect_pairs",
    "decision_is_coherent",
    "fund_side",
    "investment_to_save",
    "operation_for",
    "parse_legacy_datetime",
    "present_outcome",
    "relationship_to_save",
    "unresolved_pair_types",
]
