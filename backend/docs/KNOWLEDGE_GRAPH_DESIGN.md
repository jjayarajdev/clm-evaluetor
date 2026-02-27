# Knowledge Graph for Contract Extraction

## Overview

This document describes the implementation of a PostgreSQL-based knowledge graph to improve contract extraction accuracy by capturing relationships between entities.

## Problem Statement

Current vector-only approach limitations:
- Cannot resolve references ("The Provider" → actual company name)
- Cannot follow cross-references ("Subject to Section 5.2")
- Cannot track obligation chains (who owes what to whom, with what limits)
- Cannot infer risks from relationship patterns

## Solution: PostgreSQL Knowledge Graph

### Data Model

```sql
-- Entities (nodes)
CREATE TABLE kg_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    entity_type VARCHAR(50) NOT NULL,  -- party, clause, obligation, term, date, amount
    name VARCHAR(500) NOT NULL,
    normalized_name VARCHAR(500),  -- lowercase for matching

    properties JSONB DEFAULT '{}',  -- flexible attributes

    source_text TEXT,
    source_section VARCHAR(50),
    source_page INTEGER,
    confidence FLOAT DEFAULT 1.0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Relationships (edges)
CREATE TABLE kg_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    source_entity_id UUID NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,

    properties JSONB DEFAULT '{}',
    source_text TEXT,
    confidence FLOAT DEFAULT 1.0,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient traversal
CREATE INDEX idx_kg_entities_contract ON kg_entities(contract_id);
CREATE INDEX idx_kg_entities_type ON kg_entities(entity_type);
CREATE INDEX idx_kg_entities_name ON kg_entities(normalized_name);
CREATE INDEX idx_kg_relationships_source ON kg_relationships(source_entity_id);
CREATE INDEX idx_kg_relationships_target ON kg_relationships(target_entity_id);
CREATE INDEX idx_kg_relationships_type ON kg_relationships(relationship_type);
```

### Entity Types

| Type | Description | Example Properties |
|------|-------------|-------------------|
| `party` | Company, person | `{"role": "provider", "address": "..."}` |
| `clause` | Contract section | `{"section_number": "8.1", "title": "Indemnification"}` |
| `obligation` | What must be done | `{"type": "payment", "amount": 5000}` |
| `term` | Defined term | `{"definition": "..."}` |
| `date` | Key date | `{"date_type": "effective", "value": "2024-01-01"}` |
| `amount` | Money value | `{"value": 1000000, "currency": "USD"}` |
| `jurisdiction` | Governing law | `{"state": "Delaware"}` |
| `sla_metric` | Service level | `{"metric": "uptime", "target": "99.9%"}` |

### Relationship Types

| Type | Description | Example |
|------|-------------|---------|
| `has_party` | Contract has party | Contract → Party |
| `has_obligation` | Party has obligation | Party → Obligation |
| `benefits_from` | Party benefits | Obligation → Party |
| `references` | Clause references another | Clause → Clause |
| `limited_by` | Obligation has limit | Obligation → Amount |
| `defined_as` | Term definition | Term → Value |
| `triggered_by` | Condition triggers | Obligation → Event |
| `governed_by` | Jurisdiction | Contract → Jurisdiction |
| `amends` | Amendment modifies | Clause → Clause |
| `expires_on` | Expiration date | Contract → Date |

## Implementation Plan

### Phase 1: Database Schema
- [ ] Create migration for kg_entities and kg_relationships
- [ ] Create SQLAlchemy models
- [ ] Add indexes for graph traversal

### Phase 2: Extraction Service
- [ ] Create KnowledgeGraphExtractor service
- [ ] LLM-based entity extraction
- [ ] LLM-based relationship extraction
- [ ] Entity deduplication and merging

### Phase 3: Query Service
- [ ] Recursive CTE queries for graph traversal
- [ ] Common query patterns (resolve term, find related clauses, etc.)
- [ ] Risk pattern detection

### Phase 4: Integration
- [ ] Integrate with indexing pipeline
- [ ] Enhance Q&A with graph context
- [ ] Add graph visualization endpoint

## Key Queries

### Resolve Defined Terms
```sql
SELECT definition.name
FROM kg_entities term
JOIN kg_relationships r ON r.source_entity_id = term.id
JOIN kg_entities definition ON definition.id = r.target_entity_id
WHERE term.normalized_name = 'provider'
  AND r.relationship_type = 'defined_as'
  AND term.contract_id = :contract_id;
```

### Find All Party Obligations with Limits
```sql
SELECT
    party.name as party,
    obl.name as obligation,
    obl.properties->>'description' as description,
    limit_entity.properties->>'amount' as cap
FROM kg_entities party
JOIN kg_relationships r1 ON r1.source_entity_id = party.id
    AND r1.relationship_type = 'has_obligation'
JOIN kg_entities obl ON obl.id = r1.target_entity_id
LEFT JOIN kg_relationships r2 ON r2.source_entity_id = obl.id
    AND r2.relationship_type = 'limited_by'
LEFT JOIN kg_entities limit_entity ON limit_entity.id = r2.target_entity_id
WHERE party.contract_id = :contract_id;
```

### Find Related Clauses (Recursive)
```sql
WITH RECURSIVE clause_chain AS (
    SELECT e.id, e.name, 0 as depth, ARRAY[e.id] as path
    FROM kg_entities e
    WHERE e.name = 'Section 8.1' AND e.contract_id = :contract_id

    UNION ALL

    SELECT e2.id, e2.name, cc.depth + 1, cc.path || e2.id
    FROM clause_chain cc
    JOIN kg_relationships r ON (r.source_entity_id = cc.id OR r.target_entity_id = cc.id)
    JOIN kg_entities e2 ON e2.id = CASE
        WHEN r.source_entity_id = cc.id THEN r.target_entity_id
        ELSE r.source_entity_id
    END
    WHERE r.relationship_type IN ('references', 'amends')
      AND e2.id != ALL(cc.path)
      AND cc.depth < 5
)
SELECT DISTINCT name, depth FROM clause_chain ORDER BY depth;
```

### Detect Risk Patterns
```sql
-- Find unlimited obligations (no cap)
SELECT
    party.name as obligated_party,
    obl.name as obligation,
    'UNLIMITED' as risk
FROM kg_entities obl
JOIN kg_relationships r1 ON r1.target_entity_id = obl.id
    AND r1.relationship_type = 'has_obligation'
JOIN kg_entities party ON party.id = r1.source_entity_id
LEFT JOIN kg_relationships r2 ON r2.source_entity_id = obl.id
    AND r2.relationship_type = 'limited_by'
WHERE r2.id IS NULL
  AND obl.properties->>'type' IN ('indemnification', 'liability')
  AND obl.contract_id = :contract_id;
```

## LLM Extraction Prompt

```
Extract entities and relationships from this contract section.

ENTITIES to extract:
- party: Companies, people (include role: provider, client, vendor)
- term: Defined terms ("Provider" means..., "Effective Date" means...)
- obligation: What parties must do (include type: payment, delivery, reporting)
- amount: Money values with context
- date: Key dates (effective, expiration, deadlines)
- clause: Section references (Section 5.1, Article III)

RELATIONSHIPS to extract:
- Party [HAS_OBLIGATION] Obligation
- Obligation [BENEFITS] Party
- Clause [REFERENCES] Clause
- Term [DEFINED_AS] Entity
- Obligation [LIMITED_BY] Amount/Clause
- Obligation [TRIGGERED_BY] Event/Condition
- Contract [GOVERNED_BY] Jurisdiction

CONTRACT TEXT:
{text}

Return JSON:
{
  "entities": [...],
  "relationships": [...]
}
```

## Benefits

1. **Better Entity Resolution**: "The Provider" → "Acme Corp"
2. **Cross-Reference Understanding**: Section references resolved
3. **Obligation Tracking**: Complete chain from party to obligation to limits
4. **Risk Detection**: Pattern-based risk identification
5. **Multi-Document Reasoning**: MSA + SOW + Amendments as connected graph

## Cost Estimate

- LLM calls: ~$0.002 per contract (for KG extraction)
- Storage: ~100 entities, ~200 relationships per contract
- Query performance: <50ms for most graph traversals with proper indexes
