"""Agent implementations for the Contract Intelligence platform.

This module provides specialized AI agents for contract analysis:
- Contract Q&A Agent (SK-006): RAG-based question answering
- Metadata Extraction Agent (SK-001): Extract structured contract metadata
- Clause Extraction Agent (SK-002): Identify and extract clause types
- Obligation Tracking Agent (SK-003): Extract contractual obligations
- Risk Detection Agent (SK-004): Assess contract risks
- Renewal Monitoring Agent (SK-005): Track renewals and deadlines
"""

from app.agents.base import (
    AgentConfig,
    run_agent,
    ContractSearchTool,
    SourceCitation,
    AgentOutput,
    inject_context,
    extract_confidence,
    extract_json_from_response,
)

from app.agents.metadata_extraction import (
    ExtractedMetadata,
    MetadataField,
    extract_metadata,
    update_contract_metadata,
    register_metadata_extraction_agent,
)

from app.agents.clause_extraction import (
    ExtractedClause,
    ClauseExtractionResult,
    SUPPORTED_CLAUSE_TYPES,
    extract_clauses,
    store_extracted_clauses,
    register_clause_extraction_agent,
)

from app.agents.obligation_tracking import (
    ExtractedObligation,
    ObligationExtractionResult,
    extract_obligations,
    store_extracted_obligations,
    register_obligation_tracking_agent,
)

from app.agents.risk_detection import (
    RiskFactor,
    RiskAssessmentResult,
    RISK_CATEGORIES,
    assess_risk,
    update_contract_risk,
    register_risk_detection_agent,
)

from app.agents.renewal_monitoring import (
    RenewalTerms,
    RenewalMonitoringResult,
    analyze_renewal_terms,
    update_contract_renewal,
    register_renewal_monitoring_agent,
)

from app.agents.contract_qa import (
    QAResponse,
    ask_question,
    suggest_questions,
    register_contract_qa_agent,
)

from app.agents.sla_extraction import (
    ExtractedSLA,
    SLAExtractionResult,
    extract_slas,
    store_extracted_slas,
    register_sla_extraction_agent,
)


def register_all_agents() -> None:
    """Register all agents with the orchestrator.

    Call this at application startup to ensure all agents are available.
    """
    register_metadata_extraction_agent()
    register_clause_extraction_agent()
    register_obligation_tracking_agent()
    register_risk_detection_agent()
    register_renewal_monitoring_agent()
    register_contract_qa_agent()
    register_sla_extraction_agent()


__all__ = [
    # Base utilities
    "AgentConfig",
    "run_agent",
    "ContractSearchTool",
    "SourceCitation",
    "AgentOutput",
    "inject_context",
    "extract_confidence",
    "extract_json_from_response",
    # Metadata extraction
    "ExtractedMetadata",
    "MetadataField",
    "extract_metadata",
    "update_contract_metadata",
    "register_metadata_extraction_agent",
    # Clause extraction
    "ExtractedClause",
    "ClauseExtractionResult",
    "SUPPORTED_CLAUSE_TYPES",
    "extract_clauses",
    "store_extracted_clauses",
    "register_clause_extraction_agent",
    # Obligation tracking
    "ExtractedObligation",
    "ObligationExtractionResult",
    "extract_obligations",
    "store_extracted_obligations",
    "register_obligation_tracking_agent",
    # Risk detection
    "RiskFactor",
    "RiskAssessmentResult",
    "RISK_CATEGORIES",
    "assess_risk",
    "update_contract_risk",
    "register_risk_detection_agent",
    # Renewal monitoring
    "RenewalTerms",
    "RenewalMonitoringResult",
    "analyze_renewal_terms",
    "update_contract_renewal",
    "register_renewal_monitoring_agent",
    # Contract Q&A
    "QAResponse",
    "ask_question",
    "suggest_questions",
    "register_contract_qa_agent",
    # SLA extraction
    "ExtractedSLA",
    "SLAExtractionResult",
    "extract_slas",
    "store_extracted_slas",
    "register_sla_extraction_agent",
    # Registration
    "register_all_agents",
]
