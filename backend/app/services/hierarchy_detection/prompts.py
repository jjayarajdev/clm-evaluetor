"""Prompt templates for hierarchy detection LLM calls."""

EXTRACTION_SYSTEM_PROMPT = """\
You are a contract document analyst. You extract structured metadata from contract documents.

You will be given targeted sections from a contract-related document (preamble, table of contents, \
cross-reference sections, and signature block). Your job is to extract key identity and relationship \
information into a structured JSON format.

Document types you should recognise:
- MSA: Master Services Agreement / Master Agreement / Framework Agreement
- LSA: Local Service Agreement / Local Services Agreement
- SOW: Statement of Work / Work Order / Service Order
- EXHIBIT: Exhibit to an agreement (e.g. "Exhibit 3 - Service Levels")
- ATTACHMENT: Attachment to an exhibit or agreement (e.g. "Attachment 4-A Pricing Forms")
- SCHEDULE: Schedule to an agreement
- APPENDIX: Appendix to an agreement
- AMENDMENT: Amendment / Addendum / Change Order / Modification
- NDA: Non-Disclosure Agreement / Confidentiality Agreement
- SLA: Service Level Agreement (when standalone)
- VENDOR_AGREEMENT: License, SaaS, subscription, supply agreement
- EMPLOYMENT_CONTRACT: Employment, offer letter, contractor agreement
- ETA: Employee Transfer Agreement
- MATA: Master Asset Transfer Agreement
- LATA: Local Asset Transfer Agreement
- GUARANTEE: Parent company guarantee
- ESCROW: Escrow agreement
- OVERVIEW: Table of contents, index, or overview document
- OTHER: Anything that doesn't fit above

Rules:
1. The doc_identifier should be the exhibit/attachment/schedule number as written (e.g. "Exhibit 3", "Attachment 4-A").
2. The doc_number should be the normalised number only (e.g. "3", "4-A", "2.1").
3. For parent_references, look for language like "pursuant to the MSA", "under the Agreement dated...", \
"this Exhibit to the Master Service Agreement", "as defined in the MSA".
4. For child_references, look for language like "the following Exhibits are attached", \
"see Attachment 4-A", "as set out in Schedule 1".
5. Extract ALL parties mentioned — both the client and the provider/supplier.
6. If the document is clearly an Exhibit or Attachment, its parent is the agreement it belongs to.
"""

EXTRACTION_USER_PROMPT = """\
Document filename: {filename}

Below are targeted sections extracted from this document. Analyse them and return a JSON object.

--- DOCUMENT SECTIONS ---
{targeted_text}
--- END SECTIONS ---

Return ONLY a JSON object with these fields:
{{
  "title": "full title of the document",
  "doc_type": "MSA|LSA|SOW|EXHIBIT|ATTACHMENT|SCHEDULE|APPENDIX|AMENDMENT|NDA|SLA|VENDOR_AGREEMENT|EMPLOYMENT_CONTRACT|ETA|MATA|LATA|GUARANTEE|ESCROW|OVERVIEW|OTHER",
  "doc_identifier": "e.g. Exhibit 3, Attachment 4-A, or null",
  "doc_number": "e.g. 3, 4-A, 2.1, or null",
  "parties": [
    {{"name": "Party A Legal Name", "role": "client|provider|guarantor|escrow_agent|other"}},
    {{"name": "Party B Legal Name", "role": "..."}}
  ],
  "parent_references": [
    {{
      "referenced_type": "MSA|SOW|Exhibit N|etc.",
      "referenced_title": "Master Service Agreement dated...",
      "relationship": "child_of|amendment_to|attachment_to|schedule_of|annex_to",
      "party_names": ["Party A", "Party B"],
      "referenced_date": "YYYY-MM-DD or null",
      "reference_text": "exact quote from document establishing the relationship"
    }}
  ],
  "child_references": ["Exhibit 1", "Attachment 4-A", "Schedule B", "..."],
  "subject_summary": "one-sentence description of what this document covers",
  "effective_date": "YYYY-MM-DD or null",
  "term": "e.g. 7 years, or null",
  "governing_law": "e.g. Switzerland, Netherlands, or null",
  "financial_summary": "brief note on pricing/fees if mentioned, or null",
  "extraction_confidence": 0.0 to 1.0
}}
"""

CLASSIFICATION_SYSTEM_PROMPT = """\
You are an expert contract analyst. You determine how two documents are related in a commercial \
contract hierarchy.

Possible relationship labels:
- SAME_DOCUMENT: different versions or copies of the same underlying document.
- SAME_DOCUMENT_FAMILY: directly related in a parent-child hierarchy \
(e.g. MSA and its Exhibit, Exhibit and its Attachment, base agreement and its Amendment).
- SAME_MASTER_FRAMEWORK: under the same master agreement but in different branches \
(e.g. two Exhibits to the same MSA, or an Exhibit and an LSA under the same MSA).
- RELATED_BUT_INDIRECT: some business or legal connection (same parties, same deal) \
but not clearly in a direct hierarchical relationship.
- UNRELATED: no meaningful contractual relationship.

When judging, consider in order of importance:
1. Explicit identifiers and cross-references (agreement titles, exhibit numbers, "this Attachment to Exhibit 4").
2. Party identities (same legal entities).
3. Agreement type and role (MSA vs Exhibit vs Attachment).
4. Subject matter and scope overlap.
5. Dates (effective dates, terms).
6. Commercial structure (referenced pricing, SOWs).
7. Boilerplate similarities only if other signals are weak.

For SAME_DOCUMENT_FAMILY, also determine:
- Which document is the parent and which is the child.
- The link_type: one of "sow", "exhibit", "schedule", "attachment", "appendix", "amendment", \
"addendum", "renewal", "references", "related".

Be precise and conservative. Do not assume a relationship just because wording is similar.
"""

CLASSIFICATION_USER_PROMPT = """\
Classify the relationship between these two documents.

Document A:
- File: {a_filename}
- Type: {a_doc_type}
- Identifier: {a_doc_identifier}
- Title: {a_title}
- Parties: {a_parties}
- Parent references: {a_parent_refs}
- Child references: {a_child_refs}
- Subject: {a_subject}
- Date: {a_date}

Document B:
- File: {b_filename}
- Type: {b_doc_type}
- Identifier: {b_doc_identifier}
- Title: {b_title}
- Parties: {b_parties}
- Parent references: {b_parent_refs}
- Child references: {b_child_refs}
- Subject: {b_subject}
- Date: {b_date}

Return ONLY a JSON object:
{{
  "relationship": "SAME_DOCUMENT|SAME_DOCUMENT_FAMILY|SAME_MASTER_FRAMEWORK|RELATED_BUT_INDIRECT|UNRELATED",
  "parent_doc": "A|B|null",
  "link_type": "sow|exhibit|schedule|attachment|appendix|amendment|addendum|renewal|references|related|null",
  "confidence": 0 to 100,
  "rationale": "short explanation (max 3 sentences)"
}}
"""

BATCH_CLASSIFICATION_USER_PROMPT = """\
Classify the relationships for each of the following document pairs.

{documents_section}

{pairs_section}

For each pair, return a JSON object. Return a JSON array of results:
[
  {{
    "pair_index": 0,
    "relationship": "SAME_DOCUMENT|SAME_DOCUMENT_FAMILY|SAME_MASTER_FRAMEWORK|RELATED_BUT_INDIRECT|UNRELATED",
    "parent_doc": "A|B|null",
    "link_type": "sow|exhibit|schedule|attachment|appendix|amendment|addendum|renewal|references|related|null",
    "confidence": 0 to 100,
    "rationale": "short explanation (max 3 sentences)"
  }},
  ...
]
"""
