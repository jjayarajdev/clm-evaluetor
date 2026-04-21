"""Generate Evaluetor Business Plan PDF matching RegulAI design."""

import weasyprint

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  :root {
    --teal-dark: #1a3c40;
    --teal-mid: #2d6a6a;
    --teal-accent: #3a8a8a;
    --teal-light: #e8f4f4;
    --teal-cover: #1e4d4f;
    --text-dark: #1a1a1a;
    --text-body: #2d2d2d;
    --text-muted: #6b7280;
    --border: #e5e7eb;
    --white: #ffffff;
  }

  @page {
    size: A4;
    margin: 0;
  }

  @page content {
    margin: 80px 58px 70px 58px;
    @top-left {
      content: "Evaluetor";
      font-family: 'Inter', 'Helvetica Neue', sans-serif;
      font-size: 9pt;
      font-weight: 500;
      color: white;
      background: var(--teal-dark);
      padding: 12px 58px;
      width: 100%;
    }
    @top-right {
      content: "CONFIDENTIAL BUSINESS PLAN \\2014  2026";
      font-family: 'Inter', 'Helvetica Neue', sans-serif;
      font-size: 8pt;
      font-weight: 400;
      color: rgba(255,255,255,0.85);
      background: var(--teal-dark);
      padding: 12px 58px;
    }
    @bottom-left {
      content: "\\00A9  2026 Evaluetor Inc. All rights reserved.";
      font-family: 'Inter', 'Helvetica Neue', sans-serif;
      font-size: 7.5pt;
      color: var(--text-muted);
      border-top: 1px solid var(--border);
      padding-top: 10px;
    }
    @bottom-right {
      content: "Page " counter(page);
      font-family: 'Inter', 'Helvetica Neue', sans-serif;
      font-size: 7.5pt;
      color: var(--text-muted);
      border-top: 1px solid var(--border);
      padding-top: 10px;
    }
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: var(--text-body);
  }

  /* ─── COVER PAGE ─── */
  .cover {
    page: auto;
    width: 100%;
    height: 100vh;
    background: linear-gradient(170deg, #1a3c40 0%, #1e4d4f 45%, #2d8a7a 100%);
    color: white;
    padding: 0;
    display: flex;
    flex-direction: column;
    page-break-after: always;
  }

  .cover-content {
    padding: 100px 65px 0 65px;
    flex: 1;
  }

  .cover-brand {
    font-size: 13pt;
    font-weight: 500;
    letter-spacing: 0.5px;
    margin-bottom: 30px;
    opacity: 0.9;
  }

  .cover-title {
    font-size: 40pt;
    font-weight: 300;
    line-height: 1.15;
    margin-bottom: 28px;
    letter-spacing: -0.5px;
    max-width: 600px;
  }

  .cover-subtitle {
    font-size: 13pt;
    font-weight: 400;
    line-height: 1.5;
    opacity: 0.85;
    max-width: 550px;
    margin-bottom: 55px;
  }

  .cover-meta {
    margin-top: 10px;
  }

  .cover-meta-row {
    display: flex;
    padding: 10px 0;
    border-bottom: 1px solid rgba(255,255,255,0.15);
  }

  .cover-meta-label {
    width: 180px;
    font-size: 9.5pt;
    color: rgba(255,255,255,0.6);
    font-weight: 400;
  }

  .cover-meta-value {
    font-size: 9.5pt;
    font-weight: 500;
    color: rgba(255,255,255,0.95);
  }

  .cover-footer-band {
    background: rgba(0,0,0,0.15);
    padding: 22px 65px;
    margin-top: auto;
  }

  .cover-footer-text {
    font-size: 8pt;
    color: rgba(255,255,255,0.6);
    letter-spacing: 0.3px;
  }

  /* ─── CONTENT PAGES ─── */
  .content-page {
    page: content;
  }

  /* ─── SECTION HEADERS ─── */
  .section-label {
    font-size: 9pt;
    font-weight: 600;
    color: var(--teal-accent);
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-bottom: 12px;
    padding-top: 8px;
    border-top: 3px solid var(--teal-dark);
  }

  .section-title {
    font-size: 26pt;
    font-weight: 300;
    color: var(--text-dark);
    line-height: 1.2;
    margin-bottom: 22px;
    letter-spacing: -0.3px;
  }

  h2 {
    font-size: 15pt;
    font-weight: 500;
    color: var(--teal-mid);
    margin-top: 28px;
    margin-bottom: 12px;
    line-height: 1.3;
  }

  h3 {
    font-size: 12pt;
    font-weight: 600;
    color: var(--text-dark);
    margin-top: 20px;
    margin-bottom: 8px;
  }

  p {
    margin-bottom: 12px;
    text-align: justify;
    hyphens: auto;
  }

  /* ─── STAT BOXES ─── */
  .stat-row {
    display: flex;
    gap: 0;
    margin: 24px 0;
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
  }

  .stat-box {
    flex: 1;
    padding: 18px 16px;
    border-right: 1px solid var(--border);
  }

  .stat-box:last-child {
    border-right: none;
  }

  .stat-number {
    font-size: 28pt;
    font-weight: 300;
    color: var(--teal-dark);
    line-height: 1.1;
    margin-bottom: 8px;
  }

  .stat-desc {
    font-size: 8pt;
    color: var(--text-muted);
    line-height: 1.4;
  }

  /* ─── BLOCKQUOTES ─── */
  blockquote, .callout {
    background: var(--teal-light);
    border-left: 4px solid var(--teal-mid);
    padding: 18px 22px;
    margin: 20px 0;
    border-radius: 0 4px 4px 0;
  }

  blockquote p, .callout p {
    font-size: 10pt;
    font-weight: 500;
    color: var(--teal-dark);
    line-height: 1.55;
    margin-bottom: 0;
  }

  /* ─── TABLES ─── */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0 20px 0;
    font-size: 9pt;
  }

  thead th {
    background: var(--teal-dark);
    color: white;
    font-weight: 500;
    padding: 10px 12px;
    text-align: left;
    font-size: 8.5pt;
  }

  tbody td {
    padding: 9px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    line-height: 1.45;
  }

  tbody tr:nth-child(even) {
    background: #f9fafb;
  }

  /* ─── LISTS ─── */
  ul, ol {
    margin: 10px 0 14px 0;
    padding-left: 20px;
  }

  li {
    margin-bottom: 8px;
    line-height: 1.5;
  }

  /* ─── UTILITIES ─── */
  .page-break {
    page-break-before: always;
  }

  strong {
    font-weight: 600;
    color: var(--text-dark);
  }

  .bold-label {
    font-weight: 600;
  }

  .teal {
    color: var(--teal-mid);
  }

  .small-note {
    font-size: 8pt;
    color: var(--text-muted);
  }
</style>
</head>
<body>

<!-- ════════════════════════════════════════════ COVER ════════════════════════════════════════════ -->
<div class="cover">
  <div class="cover-content">
    <div class="cover-brand">Evaluetor</div>
    <div class="cover-title">The Agentic Contract Intelligence Platform</div>
    <div class="cover-subtitle">Replacing manual contract oversight with AI-Native, Human-in-the-Loop Post-Signature Governance</div>

    <div class="cover-meta">
      <div class="cover-meta-row">
        <span class="cover-meta-label">Document Type</span>
        <span class="cover-meta-value">Business Plan & Market Analysis</span>
      </div>
      <div class="cover-meta-row">
        <span class="cover-meta-label">Prepared</span>
        <span class="cover-meta-value">April 2026</span>
      </div>
      <div class="cover-meta-row">
        <span class="cover-meta-label">Version</span>
        <span class="cover-meta-value">1.0 &mdash; Confidential</span>
      </div>
      <div class="cover-meta-row">
        <span class="cover-meta-label">Target Market</span>
        <span class="cover-meta-value">Mid-Market & Enterprise Organizations (all industries)</span>
      </div>
      <div class="cover-meta-row" style="border-bottom:none;">
        <span class="cover-meta-label">Technology</span>
        <span class="cover-meta-value">FastAPI &middot; PostgreSQL &middot; ChromaDB &middot; GPT-4o &middot; Agentic AI &middot; React</span>
      </div>
    </div>
  </div>

  <div class="cover-footer-band">
    <div class="cover-footer-text">CONFIDENTIAL &mdash; For Authorized Recipients Only &nbsp;|&nbsp; April 2026</div>
  </div>
</div>

<!-- ════════════════════════════════════════════ EXECUTIVE SUMMARY ════════════════════════════════════════════ -->
<div class="content-page">
  <div class="section-label">EXECUTIVE SUMMARY</div>
  <div class="section-title">Executive Summary</div>

  <p>Evaluetor is a B2B Contract Intelligence platform purpose-built to solve the most expensive, invisible problem in enterprise operations: the post-signature contract management gap. While $1.24B is spent annually on CLM software that manages contracts <em>before</em> they are signed, the operational value locked inside executed contracts &mdash; obligations, SLAs, renewal terms, compliance requirements &mdash; is left unmonitored, untracked, and unenforced. The result: 9.2% of annual revenue lost to poor contract management, $2T in global value leakage, and legal teams buried in reactive firefighting instead of strategic governance.</p>

  <p>Evaluetor attacks this problem with a nine-agent AI extraction pipeline that reads every uploaded contract and automatically extracts clauses, obligations, SLAs, risks, renewals, and compliance requirements &mdash; then bridges them into a live governance layer that monitors performance, detects breaches, calculates penalties, and manages business relationships. This is not a document repository with search. It is an autonomous contract operations system that takes ownership of the post-signature lifecycle from upload to obligation fulfillment.</p>

  <div class="stat-row">
    <div class="stat-box">
      <div class="stat-number">$2.18B</div>
      <div class="stat-desc">CLM Market 2025 (CAGR 17.1%)<br>Source: Mordor Intelligence</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">$7.6B</div>
      <div class="stat-desc">AI in Legal Market 2032 (CAGR 28.5%)<br>Source: Grand View Research</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">9.2%</div>
      <div class="stat-desc">Annual Revenue Lost to Poor Contract Management<br>Source: WorldCC/IACCM</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">71%</div>
      <div class="stat-desc">Companies Still Using Manual Contract Processes<br>Source: Deloitte Legal Tech Survey</div>
    </div>
  </div>

  <blockquote>
    <p><strong>The Strategic Insight:</strong> Icertis ($2.8B valuation) owns the enterprise pre-signature workflow. DocuSign owns the signature. Ironclad owns the legal workflow UX. But nobody owns what happens <em>after</em> the contract is signed &mdash; the 3-to-10-year operational lifecycle where obligations must be met, SLAs must be tracked, renewals must be caught, and relationships must be governed. Evaluetor owns that gap &mdash; and it&rsquo;s where all the money is lost.</p>
  </blockquote>
</div>

<!-- ════════════════════════════════════════════ SECTION 1 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 1 &mdash; THE PROBLEM</div>
  <div class="section-title">The Problem: Four Compounding Crises</div>

  <h2>1.1 The Post-Signature Black Hole</h2>
  <p>Every enterprise signs thousands of contracts per year. The moment the signature is applied, the contract enters a black hole. It is stored in a shared drive, a legacy repository, or a CLM system designed for pre-signature workflows &mdash; and nobody monitors what was promised. The average Fortune 500 company manages 20,000&ndash;40,000 active contracts. Each contains obligations with deadlines, SLAs with penalty thresholds, renewal terms with notice periods, and compliance requirements with regulatory consequences. A single missed auto-renewal notice can lock an organization into an unfavorable contract for years. A single untracked SLA breach can waive penalty recovery rights worth millions.</p>

  <h2>1.2 The Legal Team Capacity Crisis</h2>
  <p>In-house legal teams are chronically understaffed relative to their contract volume. The average corporate legal department spends 50% of its time on contract-related work, yet manages only 10% of contracts proactively. The remaining 90% sit unmonitored until a crisis &mdash; a missed renewal, a compliance audit, a vendor dispute &mdash; forces reactive attention. Law departments are growing at 1.5% annually while contract volume grows at 8&ndash;12%. The gap is widening, and hiring cannot close it.</p>

  <h2>1.3 The Fragmented Tool Landscape</h2>
  <p>Most organizations use 3&ndash;5 disconnected systems to manage their contract lifecycle: a CLM for authoring, a signature platform, a shared drive for storage, spreadsheets for obligation tracking, and email for vendor communication. No single system provides a unified view from contract terms to operational performance. Data lives in silos. When a procurement team wants to know if a vendor is meeting its SLA commitments, they must manually cross-reference the contract text, the service delivery data, and the performance history &mdash; a process that takes days and is repeated hundreds of times per year.</p>

  <h2>1.4 The Relationship Governance Deficit</h2>
  <p>Contracts define business relationships, but no CLM system measures whether those relationships are healthy. Organizations track KPIs in dashboards, vendor performance in scorecards, and stakeholder satisfaction in surveys &mdash; all in separate systems with no connection to the underlying contract commitments. There is no feedback loop between what was promised in the contract and how the relationship is actually perceived by both parties. When a vendor relationship deteriorates, the warning signs are invisible until they become contractual disputes.</p>

  <table>
    <thead>
      <tr><th>Crisis</th><th>Current State</th><th>Impact</th><th>Evaluetor Solution</th></tr>
    </thead>
    <tbody>
      <tr><td>Post-Signature Black Hole</td><td>Contracts stored and forgotten after signing</td><td>9.2% revenue leakage, missed renewals, untracked obligations</td><td>9-agent AI extraction pipeline; live obligation/SLA monitoring</td></tr>
      <tr><td>Legal Capacity Gap</td><td>50% of legal time on contracts; 90% unmonitored</td><td>Reactive firefighting, compliance risk, missed deadlines</td><td>Automated extraction and governance; human oversight only for exceptions</td></tr>
      <tr><td>Fragmented Tools</td><td>3&ndash;5 disconnected systems per organization</td><td>Manual cross-referencing, no unified view, data silos</td><td>Single platform: upload &rarr; extract &rarr; monitor &rarr; govern &rarr; report</td></tr>
      <tr><td>Relationship Deficit</td><td>No connection between contract terms and relationship health</td><td>Vendor disputes, satisfaction gaps, no early warning</td><td>Governance Bridge: contracts auto-create orgs, KPIs, perception scoring</td></tr>
    </tbody>
  </table>
</div>

<!-- ════════════════════════════════════════════ SECTION 2 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 2 &mdash; THE SOLUTION</div>
  <div class="section-title">The Solution: Agentic Contract Intelligence</div>

  <p>Evaluetor replaces manual post-signature oversight with a four-layer technology stack that reads contracts, extracts intelligence, monitors performance, and governs business relationships &mdash; with humans in the loop for judgment and exception handling. This is not a contract repository with AI search bolted on. It is an autonomous operations platform that takes ownership of the post-signature lifecycle.</p>

  <h2>2.1 Layer 1: The Nine-Agent AI Extraction Pipeline</h2>
  <p>When a contract is uploaded, Evaluetor&rsquo;s Agent Squad processes it through nine specialized AI agents, each purpose-built for a specific extraction task. The pipeline runs in minutes, not days.</p>

  <table>
    <thead>
      <tr><th>Agent</th><th>Role</th><th>Key Actions</th><th>Output</th></tr>
    </thead>
    <tbody>
      <tr><td>Metadata Extraction</td><td>Identifies parties, dates, values, contract type</td><td>LLM-powered parsing with counterparty cleaning, currency validation, template detection</td><td>Structured metadata for every contract</td></tr>
      <tr><td>Clause Extraction</td><td>Extracts and classifies contract language</td><td>17+ clause types with semantic classification, section mapping, page-level highlighting</td><td>Searchable clause library across all contracts</td></tr>
      <tr><td>Obligation Tracking</td><td>Identifies commitments with deadlines and parties</td><td>Deadline parsing (fixed, recurring, relative), party assignment, consequence extraction</td><td>Obligation register with RAG status tracking</td></tr>
      <tr><td>SLA Extraction</td><td>Extracts metrics, targets, and penalties</td><td>Target values, warning thresholds, penalty calculations, measurement periods</td><td>SLA compliance dashboard with breach detection</td></tr>
      <tr><td>Risk Detection</td><td>Assesses 10 risk categories</td><td>Content-weighted scoring across unlimited liability, weak termination, missing limitation</td><td>Portfolio risk dashboard with category breakdown</td></tr>
      <tr><td>Renewal Monitoring</td><td>Detects auto-renewal and notice periods</td><td>Notice date calculation, renewal type classification, at-risk flagging</td><td>Renewal calendar with automated alerts</td></tr>
      <tr><td>Schema Extraction</td><td>Extracts fields for 15 contract types</td><td>1,235 extractable fields across 133 sections (MSA, NDA, SOW, Employment, etc.)</td><td>Structured data competitive with enterprise CLM</td></tr>
      <tr><td>Regulatory Extraction</td><td>Identifies compliance requirements</td><td>10 obligation categories, regulatory obligation tracking</td><td>Compliance gap detection dashboard</td></tr>
      <tr><td>Intent Router</td><td>Routes user queries to specialized handlers</td><td>5 structured query categories + RAG-powered Q&amp;A with LLM visualizations</td><td>Conversational AI with auto-generated charts</td></tr>
    </tbody>
  </table>

  <ul>
    <li><strong>Parallel Processing:</strong> All nine agents run concurrently, producing results in minutes per contract.</li>
    <li><strong>Observability:</strong> Full Langfuse tracing for every LLM call &mdash; cost, latency, and quality metrics visible to operators.</li>
    <li><strong>Accuracy:</strong> 90%+ extraction accuracy with progressive prefix matching for document highlighting.</li>
    <li><strong>Scale:</strong> Tested on 600+ contracts simultaneously; designed for enterprise portfolios of 40,000+ contracts.</li>
  </ul>

  <h2>2.2 Layer 2: The Post-Signature Governance Engine</h2>
  <p>After extraction, Evaluetor&rsquo;s governance engine takes over the operational lifecycle:</p>
  <ul>
    <li><strong>SLA Monitoring:</strong> Compare contracted vs. actual performance with automated breach detection and service credit calculation.</li>
    <li><strong>Obligation Tracking:</strong> RAG status (Red/Amber/Green) for every obligation, with deadline alerts and compliance rate dashboards.</li>
    <li><strong>Milestone Tracking:</strong> Project milestone health with variance alerts and escalation workflows.</li>
    <li><strong>Compliance Monitoring:</strong> Industry-aware compliance gap detection against configurable rule sets.</li>
    <li><strong>Workflow Automation:</strong> 14+ automated action types triggered by events (threshold breaches, deadline proximity, status changes).</li>
    <li><strong>Alert Lifecycle:</strong> Full acknowledge &rarr; resolve &rarr; escalate &rarr; dismiss lifecycle with severity classification and trend analysis.</li>
  </ul>
</div>

<!-- ════════════════════ SECTION 2 (continued) ════════════════════ -->
<div class="content-page page-break">
  <h2>2.3 Layer 3: The Governance Bridge <span style="font-weight:300; font-size:11pt; color: var(--text-muted);">(Unique Capability)</span></h2>
  <p>No competitor has this. When Evaluetor extracts contract intelligence, it doesn&rsquo;t stop at a dashboard. It automatically creates the operational governance structure:</p>
  <ul>
    <li>Contract upload <strong>auto-creates</strong> the counterparty organization.</li>
    <li>SLA extraction <strong>auto-creates</strong> KPI definitions with targets and thresholds.</li>
    <li>Obligation extraction <strong>auto-creates</strong> business relationship tracking.</li>
    <li>Gap detection <strong>auto-creates</strong> improvement points with action items.</li>
  </ul>
  <p>This automated pipeline &mdash; from contract upload to relationship governance &mdash; eliminates the manual setup work that makes governance programs die in Excel spreadsheets.</p>

  <h2>2.4 Layer 4: Relationship Intelligence <span style="font-weight:300; font-size:11pt; color: var(--text-muted);">(Unique Capability)</span></h2>
  <p>Evaluetor&rsquo;s Relationship Governance module measures the health of business relationships from both sides:</p>
  <ul>
    <li><strong>Internal Perception Scoring:</strong> How your team perceives the vendor/partner relationship.</li>
    <li><strong>External Perception Scoring:</strong> How the counterparty perceives the relationship (via external survey portal).</li>
    <li><strong>Perception Gap Analysis:</strong> Automated severity classification when internal and external scores diverge.</li>
    <li><strong>Improvement Tracking:</strong> Auto-generated improvement points with action items and owners.</li>
    <li><strong>Multi-Party Surveys:</strong> Full survey lifecycle with template management and token-based external access.</li>
  </ul>

  <blockquote>
    <p>This is the only CLM platform that measures relationship health from both perspectives and connects it to the underlying contract performance.</p>
  </blockquote>
</div>

<!-- ════════════════════════════════════════════ SECTION 3 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 3 &mdash; MARKET OPPORTUNITY</div>
  <div class="section-title">Market Opportunity</div>

  <p>Evaluetor addresses a precisely defined, underserved segment at the intersection of three large and growing markets: Contract Lifecycle Management, AI-powered Legal Technology, and Business Relationship Management.</p>

  <h2>3.1 Total Addressable Market (TAM)</h2>

  <div class="stat-row">
    <div class="stat-box">
      <div class="stat-number">$2.18B</div>
      <div class="stat-desc">CLM Software Market (2025, CAGR 17.1%)<br>Mordor Intelligence</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">$7.6B</div>
      <div class="stat-desc">AI in Legal Technology (2032, CAGR 28.5%)<br>Grand View Research</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">$1.24B</div>
      <div class="stat-desc">CLM Market Revenue 2025<br>Competitive Feature Comparison</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">$21.5B</div>
      <div class="stat-desc">Legal Tech Market 2027<br>Gartner</div>
    </div>
  </div>

  <h2>3.2 Serviceable Addressable Market (SAM)</h2>
  <p>Evaluetor&rsquo;s initial focus is mid-market and enterprise organizations with significant post-signature contract management needs: IT outsourcing, managed services, procurement-heavy industries, and regulated sectors. The SAM is concentrated in organizations with $50M&ndash;$5B in contracted spend &mdash; large enough to feel the pain of manual oversight, yet underserved by enterprise CLM vendors with 12&ndash;18 month implementations and $100K+ deployment costs.</p>

  <table>
    <thead>
      <tr><th>Customer Segment</th><th>Approx. Count</th><th>Annual CLM Spend Est.</th><th>Evaluetor Target</th></tr>
    </thead>
    <tbody>
      <tr><td>SMB (&lt;$100M revenue)</td><td>~50,000</td><td>$10K&ndash;$50K/year</td><td>Self-serve SaaS tier</td></tr>
      <tr><td>Mid-Market ($100M&ndash;$1B)</td><td>~12,000</td><td>$50K&ndash;$250K/year</td><td>Core revenue target</td></tr>
      <tr><td>Large Enterprise ($1B&ndash;$10B)</td><td>~3,500</td><td>$250K&ndash;$1M/year</td><td>Enterprise managed service</td></tr>
      <tr><td>Global Enterprise (&gt;$10B)</td><td>~500</td><td>$1M&ndash;$5M/year</td><td>Partnership/white-label</td></tr>
    </tbody>
  </table>

  <p>With 12,000 mid-market targets and a blended ACV of $120,000, the SAM is approximately $1.44B annually. At 5% market penetration over 5 years, the SOM (Serviceable Obtainable Market) is $72M ARR &mdash; a credible, venture-backable target.</p>

  <h2>3.3 Why Now: The Post-Signature Inflection Point</h2>
  <p>Four forces are converging in 2026 to make this the optimal moment to launch:</p>
  <ul>
    <li><strong>Agentic AI maturity:</strong> Gartner projects 40% of enterprise applications will include task-specific AI agents by 2026 &mdash; up from &lt;5% in 2025. The infrastructure for production-grade nine-agent extraction pipelines now exists.</li>
    <li><strong>Post-signature awareness:</strong> WorldCC/IACCM research showing 9.2% revenue leakage from poor contract management has finally reached C-suite awareness. CFOs are demanding visibility into contracted obligations.</li>
    <li><strong>CLM market consolidation:</strong> Workday acquired Evisort, Haveli took majority stake in Sirion, Conga acquired PROS Holdings, Agiloft acquired Screens. The incumbents are focused on integration, creating a window for AI-native entrants.</li>
    <li><strong>Compliance complexity explosion:</strong> ESG reporting mandates, AI governance requirements, data privacy regulations, and supply chain due diligence are multiplying the compliance obligations embedded in every contract. Manual tracking is no longer viable.</li>
  </ul>
</div>

<!-- ════════════════════════════════════════════ SECTION 4 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 4 &mdash; COMPETITIVE POSITIONING</div>
  <div class="section-title">Competitive Landscape &amp; Positioning</div>

  <h2>4.1 The White Space: Post-Signature + Relationship Governance</h2>
  <p>Evaluetor is designed to own the white space that every existing CLM vendor leaves unaddressed: what happens after the contract is signed, and whether the business relationship it governs is actually healthy.</p>

  <table>
    <thead>
      <tr><th>Company</th><th>Role</th><th>Strength</th><th>Gap Evaluetor Fills</th><th>Relationship</th></tr>
    </thead>
    <tbody>
      <tr><td>Icertis</td><td>Enterprise CLM Platform (Vera AI)</td><td>$2.8B valuation; deep SAP/Workday integration</td><td>12&ndash;18 month implementations; no relationship governance</td><td>Complement (different segment)</td></tr>
      <tr><td>DocuSign</td><td>Signature + IAM</td><td>Universal e-signature adoption; Iris AI</td><td>Bolt-on CLM; no post-signature monitoring</td><td>Complement (signature partner)</td></tr>
      <tr><td>Ironclad</td><td>Legal Operating System</td><td>Best-in-class workflow UX; Rivet (6 agents)</td><td>Weak post-signature; no SLA monitoring</td><td>Complement (pre-signature)</td></tr>
      <tr><td>Sirion</td><td>AI-Native Contract OS</td><td>Highest Gartner execution score; agentOS</td><td>Dense UI; no perception gap scoring</td><td>Direct competitor (post-signature)</td></tr>
      <tr><td>Luminance</td><td>Autonomous Legal AI</td><td>AI-to-AI negotiation (Autopilot)</td><td>No post-signature management</td><td>Complement (negotiation)</td></tr>
      <tr><td>Agiloft</td><td>No-Code CLM</td><td>Extreme customization; Screens acquisition</td><td>No relationship governance</td><td>Complement (no-code)</td></tr>
      <tr><td>Conga</td><td>Revenue Lifecycle</td><td>PROS pricing intelligence; 1,400+ models</td><td>Less AI-native; no relationship governance</td><td>Complement (revenue focus)</td></tr>
      <tr><td><strong>Evaluetor</strong></td><td><strong>Agentic Contract Intelligence + Relationship Governance</strong></td><td><strong>9-agent pipeline; governance bridge; perception scoring; unlimited users</strong></td><td><strong>IS the gap &mdash; owns post-signature + relationship health</strong></td><td><strong>Unique positioning</strong></td></tr>
    </tbody>
  </table>

  <h2>4.2 Competitive Differentiation Matrix</h2>

  <table>
    <thead>
      <tr><th>Dimension</th><th>Market Leader(s)</th><th>Evaluetor Position</th></tr>
    </thead>
    <tbody>
      <tr><td>Pre-Signature (Authoring/Negotiation)</td><td>Ironclad, Luminance, Icertis</td><td>Not implemented (deliberate focus choice)</td></tr>
      <tr><td>Post-Signature Management</td><td>Sirion, Evaluetor</td><td><strong>Strong</strong> &mdash; SLAs, obligations, compliance, renewals, milestones</td></tr>
      <tr><td>AI Extraction</td><td>Sirion, Evaluetor, Conga</td><td><strong>Strong</strong> &mdash; 9+ agents, 15 schemas, 1,235 fields</td></tr>
      <tr><td>Governance Bridge</td><td><strong>Evaluetor</strong></td><td><strong>Unique</strong> &mdash; automated contract &rarr; org/relationship/KPI pipeline</td></tr>
      <tr><td>Perception Gap Scoring</td><td><strong>Evaluetor</strong></td><td><strong>Unique</strong> &mdash; dual-perspective with severity classification</td></tr>
      <tr><td>Unlimited-Users Pricing</td><td><strong>Evaluetor</strong></td><td><strong>Unique</strong> &mdash; no major CLM vendor offers this</td></tr>
      <tr><td>Time-to-Value</td><td>Evaluetor, Luminance</td><td><strong>Fastest</strong> &mdash; upload to insights in hours, not months</td></tr>
      <tr><td>LLM Observability</td><td><strong>Evaluetor</strong> (Langfuse)</td><td><strong>Unique</strong> &mdash; no competitor offers comparable agent tracing</td></tr>
    </tbody>
  </table>

  <blockquote>
    <p><strong>The Positioning in One Sentence:</strong> Every CLM vendor fights over who owns the workflow <em>before</em> the signature. Evaluetor owns everything that happens <em>after</em> &mdash; where 9.2% of revenue is lost, where relationships succeed or fail, and where contracts either deliver their promised value or silently decay.</p>
  </blockquote>
</div>

<!-- ════════════════════════════════════════════ SECTION 5 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 5 &mdash; BUSINESS MODEL</div>
  <div class="section-title">Business Model</div>

  <h2>5.1 Revenue Architecture</h2>
  <p>Evaluetor operates a three-tier SaaS model with <strong>unlimited-users pricing</strong> &mdash; a genuine market differentiator. While every competitor charges per seat ($50&ndash;$150/user/month), Evaluetor charges per contract portfolio, eliminating the barrier to cross-functional adoption.</p>

  <table>
    <thead>
      <tr><th>Tier</th><th>Product</th><th>Target Customer</th><th>Pricing Model</th><th>Est. ACV</th></tr>
    </thead>
    <tbody>
      <tr><td>Tier 1 Starter</td><td>Upload + AI Extraction + Basic Dashboards</td><td>SMB (&lt;$100M revenue), 1&ndash;2 departments</td><td>SaaS subscription per contract volume band. Unlimited users.</td><td>$20K&ndash;$60K</td></tr>
      <tr><td>Tier 2 Professional</td><td>Full Platform &mdash; Extraction + Governance + Compliance + Workflows + Relationship Management</td><td>Mid-market ($100M&ndash;$1B), multi-department adoption</td><td>Annual contract based on portfolio size + per-analysis fee for deep extraction</td><td>$80K&ndash;$250K</td></tr>
      <tr><td>Tier 3 Enterprise</td><td>Full Platform + Custom Integrations + Dedicated Success + SLA on AI Accuracy</td><td>Large enterprise (&gt;$1B), multi-BU deployment</td><td>Multi-year enterprise contract. Custom pricing + outcome-based bonuses</td><td>$300K&ndash;$1M+</td></tr>
      <tr><td>Add-On Services</td><td>Integration Implementation, Contract Migration, Compliance Audit, Governance Workshop</td><td>All tiers</td><td>Project-based SOW, $15K&ndash;$100K per engagement</td><td>Variable</td></tr>
    </tbody>
  </table>

  <h2>5.2 Unit Economics</h2>
  <p>The core economics are compelling because the AI extraction pipeline is a shared asset &mdash; built once, applied to every contract. Marginal cost per additional contract is dominated by OpenAI API costs (~$0.30&ndash;$0.80 per contract analysis), not human labor.</p>

  <div class="stat-row">
    <div class="stat-box">
      <div class="stat-number">~82%</div>
      <div class="stat-desc">Gross Margin (Tier 2/3 at scale)<br>Post-automation of extraction pipeline</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">&lt;12 mo</div>
      <div class="stat-desc">Payback Period (Tier 2 Professional)<br>Based on $150K ACV, $100K CAC</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">94%+</div>
      <div class="stat-desc">Target Net Revenue Retention<br>Contracts never go away; portfolios grow</div>
    </div>
    <div class="stat-box">
      <div class="stat-number">3&ndash;5x</div>
      <div class="stat-desc">Expansion ARR Multiplier (Y1&rarr;Y3)<br>Via department/BU expansion per customer</div>
    </div>
  </div>

  <h2>5.3 Go-to-Market Strategy</h2>
  <p>Evaluetor will enter the market through three parallel channels, prioritized by speed of trust establishment:</p>
  <ul>
    <li><strong>Channel 1 &mdash; Direct Consultative Sales:</strong> Target mid-market organizations in IT outsourcing, financial services, healthcare, and manufacturing (highest contract management burden). ICP: VP of Procurement, General Counsel, Chief Compliance Officer. Entry via free 90-day contract audit &mdash; upload your portfolio, see your risk exposure.</li>
    <li><strong>Channel 2 &mdash; Technology Partnerships:</strong> Position Evaluetor as the post-signature intelligence layer for existing CLM, ERP, and ITSM platforms. Certified integration with ServiceNow, Salesforce, and SAP creates a distribution channel where the platform vendor&rsquo;s sales team becomes Evaluetor&rsquo;s sales team.</li>
    <li><strong>Channel 3 &mdash; Consulting &amp; Advisory Partnerships:</strong> Partner with Big 4 consulting firms and boutique legal operations consultancies who advise on contract governance. The Governance Bridge capability provides the automated infrastructure their governance frameworks have always lacked.</li>
  </ul>
</div>

<!-- ════════════════════════════════════════════ SECTION 6 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 6 &mdash; FINANCIAL PROJECTIONS</div>
  <div class="section-title">Financial Projections (5-Year)</div>

  <p>The following projections assume a Series A raise of $10M in 2026, with product launch in Q3 2026, first paying customers in Q4 2026, and a 30-month path to cash-flow breakeven.</p>

  <table>
    <thead>
      <tr><th>Metric</th><th>2026 (Launch)</th><th>2027 (Y1 Full)</th><th>2028 (Y2)</th><th>2029 (Y3)</th><th>2030 (Y4)</th></tr>
    </thead>
    <tbody>
      <tr><td>ARR (End of Year)</td><td>$0.6M</td><td>$3.2M</td><td>$9.5M</td><td>$22M</td><td>$45M</td></tr>
      <tr><td># Customers</td><td>4</td><td>18</td><td>48</td><td>95</td><td>170</td></tr>
      <tr><td>Blended ACV</td><td>$150K</td><td>$178K</td><td>$198K</td><td>$232K</td><td>$265K</td></tr>
      <tr><td>Gross Margin %</td><td>52%</td><td>65%</td><td>74%</td><td>80%</td><td>83%</td></tr>
      <tr><td>Headcount</td><td>15</td><td>35</td><td>65</td><td>110</td><td>165</td></tr>
      <tr><td>Net ARR Retention</td><td>N/A</td><td>110%</td><td>116%</td><td>122%</td><td>125%</td></tr>
      <tr><td>Cash Flow</td><td>-$3.5M</td><td>-$5.8M</td><td>-$1.8M</td><td>+$3.5M</td><td>+$14M</td></tr>
    </tbody>
  </table>

  <h2>6.1 Use of Funds ($10M Series A)</h2>

  <table>
    <thead>
      <tr><th>Category</th><th>Amount</th><th>%</th><th>Key Activities</th></tr>
    </thead>
    <tbody>
      <tr><td>Product &amp; Engineering</td><td>$4.0M</td><td>40%</td><td>Enterprise integrations (ServiceNow, Salesforce, SAP); contract authoring module; visual workflow builder; SOC 2 certification</td></tr>
      <tr><td>Sales &amp; Marketing</td><td>$2.5M</td><td>25%</td><td>Enterprise sales team (3 AEs); product marketing; industry conferences; free audit lead generation</td></tr>
      <tr><td>AI &amp; Data Science</td><td>$1.5M</td><td>15%</td><td>Fine-tuned extraction models; accuracy benchmarking; private LLM deployment option; advanced analytics</td></tr>
      <tr><td>Customer Success &amp; Ops</td><td>$1.0M</td><td>10%</td><td>Onboarding specialists; implementation team; technical support; contract migration tooling</td></tr>
      <tr><td>G&amp;A / Working Capital</td><td>$1.0M</td><td>10%</td><td>Legal, finance, insurance, office infrastructure, 18-month runway buffer</td></tr>
    </tbody>
  </table>
</div>

<!-- ════════════════════════════════════════════ SECTION 7 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 7 &mdash; EXECUTION ROADMAP</div>
  <div class="section-title">Execution Roadmap</div>

  <table>
    <thead>
      <tr><th>Phase</th><th>Timeline</th><th>Key Milestones</th><th>Success Criteria</th></tr>
    </thead>
    <tbody>
      <tr><td>Phase 0: Foundation</td><td>Q2&ndash;Q3 2026</td><td>Incorporate; close pre-seed/seed ($2M). Hire founding team (CTO, Head of Product, 2 senior engineers). Complete SOC 2 Type I. Finish enterprise integration framework.</td><td>Platform handles 10,000+ contracts. 3+ pilot customers onboarded. SOC 2 Type I certified.</td></tr>
      <tr><td>Phase 1: Pilot</td><td>Q4 2026&ndash;Q1 2027</td><td>Sign 3&ndash;5 pilot customers (Tier 2 Professional). Conduct free 90-day contract audits. Deploy governance bridge at pilot sites. Collect NPS and time-savings data.</td><td>Zero critical bugs. Documented 50%+ reduction in manual contract review time. 2+ pilots convert to paid.</td></tr>
      <tr><td>Phase 2: Scale</td><td>Q2&ndash;Q4 2027</td><td>Launch Tier 1 self-serve SaaS. Sign first Tier 3 enterprise customers. Launch ServiceNow and Salesforce integrations. Build visual workflow UI. Close Series A ($10M). Reach 18+ paying customers.</td><td>$3M+ ARR. Integration partnerships signed. Net Revenue Retention &gt;110%.</td></tr>
      <tr><td>Phase 3: Platform</td><td>2028&ndash;2029</td><td>Launch contract authoring module. Expand to 10+ enterprise integrations. Build AI redlining. Launch industry-specific compliance packs. Evaluate Series B ($25M+).</td><td>$22M+ ARR. 95+ customers. Path to cash-flow positive visible in 18 months.</td></tr>
      <tr><td>Phase 4: Exit / Scale</td><td>2030+</td><td>Full CLM lifecycle coverage. International expansion (UK, EU, APAC). Private LLM deployment for regulated industries. Strategic M&amp;A opportunities.</td><td>$45M+ ARR. Strategic acquisition discussions. Potential IPO consideration at $500M+ valuation.</td></tr>
    </tbody>
  </table>
</div>

<!-- ════════════════════════════════════════════ SECTION 8 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 8 &mdash; TEAM &amp; RISKS</div>
  <div class="section-title">Team Architecture &amp; Risk Mitigation</div>

  <h2>8.1 Founding Team Requirements</h2>
  <p>Evaluetor&rsquo;s differentiation is the rare combination of deep contract management domain knowledge, enterprise AI engineering capability, and relationship governance design. The founding team must cover four critical competencies:</p>

  <table>
    <thead>
      <tr><th>Role</th><th>Background Required</th><th>Why Critical</th></tr>
    </thead>
    <tbody>
      <tr><td>CEO / Chief Strategy Officer</td><td>10+ years in enterprise software; legal tech, procurement, or GRC domain. Consulting or CLM vendor experience.</td><td>CLM is a trust sale. The CEO must have credibility with General Counsel, CPOs, and CCOs &mdash; and the ability to navigate enterprise procurement cycles.</td></tr>
      <tr><td>CTO / Chief Architect</td><td>Full-stack with AI/ML depth; FastAPI or similar async Python frameworks; PostgreSQL; vector databases; LLM orchestration</td><td>The nine-agent extraction pipeline is the product. Technical depth must match the complexity of multi-agent orchestration and enterprise-grade data isolation.</td></tr>
      <tr><td>Head of Product / Domain Expert</td><td>10+ years in contract management, legal operations, or procurement. Former CLM user or implementer.</td><td>This person IS the domain knowledge that Evaluetor digitizes. They validate agent accuracy, define governance workflows, and serve as the ultimate human-in-the-loop authority.</td></tr>
      <tr><td>VP of Revenue / Partnerships</td><td>Enterprise SaaS sales in legal tech, procurement tech, or GRC. Existing relationships with consulting firms and CLM ecosystem partners.</td><td>Distribution in legal tech requires trust. A VP who can open doors at mid-market organizations is worth 18 months of cold outreach.</td></tr>
    </tbody>
  </table>

  <h2>8.2 Key Risks and Mitigations</h2>

  <table>
    <thead>
      <tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Mitigation</th></tr>
    </thead>
    <tbody>
      <tr><td>Icertis/Sirion add relationship governance</td><td>Medium</td><td>High</td><td>First-mover advantage on governance bridge + perception scoring. By the time incumbents build it, Evaluetor has 2+ years of customer data and workflow refinement.</td></tr>
      <tr><td>Enterprise sales cycles extend beyond 12 months</td><td>High</td><td>Medium</td><td>Enter via free 90-day contract audit &mdash; delivers immediate value before contract negotiation. Consulting partner channel accelerates trust.</td></tr>
      <tr><td>AI extraction accuracy falls below expectations</td><td>Medium</td><td>Very High</td><td>Human-in-the-loop review for all critical extractions. Langfuse observability for continuous accuracy monitoring. Customer-specific tuning during onboarding.</td></tr>
      <tr><td>OpenAI API costs increase significantly</td><td>Medium</td><td>Medium</td><td>Multi-model architecture (GPT-4o, Claude, fine-tuned open-source). Private LLM deployment option for enterprise tier. Cost per contract analysis already &lt;$1.</td></tr>
      <tr><td>CLM market consolidation eliminates whitespace</td><td>Low</td><td>High</td><td>Relationship governance capability has no CLM analog. Even if acquired, the governance bridge is a feature any acquirer would want. Position for strategic acquisition as a positive outcome.</td></tr>
      <tr><td>Compliance/security certification delays</td><td>Medium</td><td>Medium</td><td>Begin SOC 2 Type I in Phase 0. Hire compliance-experienced security lead. Use established infrastructure (AWS, PostgreSQL) with documented controls.</td></tr>
    </tbody>
  </table>
</div>

<!-- ════════════════════════════════════════════ SECTION 9 ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div class="section-label">SECTION 9 &mdash; THE INVESTMENT CASE</div>
  <div class="section-title">The Investment Case</div>

  <p>Evaluetor is not a speculative bet on AI in legal. It is a solution to a structural operational problem in a $2.18 trillion managed-services economy where every business relationship is governed by a contract, and 9.2% of the value in those contracts is lost to poor post-signature management.</p>

  <h2>Why This Business Wins:</h2>

  <ul>
    <li><strong>Structural tailwind:</strong> 71% of organizations still use manual contract processes. Digital transformation in legal operations is 5&ndash;10 years behind finance and HR. The adoption curve is early and accelerating.</li>
    <li><strong>Ecosystem fit:</strong> Every CLM vendor focuses on pre-signature. Every signature vendor focuses on execution. Every ERP vendor focuses on financial data. Evaluetor is a complement to all of them &mdash; owning the post-signature intelligence layer that none of them provide. This makes partnership the path of least resistance.</li>
    <li><strong>Unique capabilities as moat:</strong> The Governance Bridge (automated contract &rarr; organization &rarr; KPI &rarr; relationship pipeline) and Perception Gap Scoring (dual-perspective with severity classification) have no competitive analog. Once deployed, switching to a competitor means losing the entire governance infrastructure.</li>
    <li><strong>Net Revenue Retention &gt;120%:</strong> Contracts don&rsquo;t go away. Portfolios grow. Departments adopt. BU expansion is natural. The unlimited-users pricing model eliminates seat-cost friction for cross-functional adoption. NRR exceeds 120% because contract portfolios compound.</li>
    <li><strong>Regulation is the contract:</strong> Unlike SaaS products that compete on features, Evaluetor&rsquo;s value proposition is underwritten by the contracts themselves. As long as organizations sign contracts with obligations, SLAs, and renewal terms, Evaluetor is needed. The addressable problem is non-discretionary.</li>
    <li><strong>Acquisition optionality:</strong> Icertis ($2.8B valuation), SAP, ServiceNow, Salesforce, and Workday all have strategic reasons to own post-signature contract intelligence. A 5x revenue exit at $225M ARR implies a $1.1B+ transaction by 2031.</li>
  </ul>

  <blockquote>
    <p><strong>The Core Thesis in One Sentence:</strong> Every organization in the world signs contracts that contain promises &mdash; obligations, SLAs, deadlines, compliance requirements &mdash; and the tools that manage those contracts were designed to get them signed, not to ensure the promises are kept. Evaluetor is the company that was built to close that gap, at exactly the moment when agentic AI makes it possible to do so at scale.</p>
  </blockquote>
</div>

<!-- ════════════════════════════════════════════ SOURCES ════════════════════════════════════════════ -->
<div class="content-page page-break">
  <div style="border-top: 3px solid var(--teal-dark); padding-top: 8px; margin-bottom: 20px;">
    <h2 style="margin-top: 0;">Sources &amp; References</h2>
  </div>

  <ol style="font-size: 9pt; line-height: 1.7;">
    <li>Mordor Intelligence &mdash; Contract Lifecycle Management Market Size &amp; Share Analysis (2025&ndash;2030)</li>
    <li>Grand View Research &mdash; AI in Legal Technology Market Report (2024&ndash;2032)</li>
    <li>WorldCC/IACCM &mdash; The Cost of Poor Contract Management (2024)</li>
    <li>Gartner &mdash; Magic Quadrant for Contract Life Cycle Management (2025)</li>
    <li>Deloitte &mdash; Legal Department Operations Survey: Contract Management (2025)</li>
    <li>Icertis &mdash; Company Valuation and Funding History (Crunchbase)</li>
    <li>Forrester &mdash; The Forrester Wave: Contract Lifecycle Management (2025)</li>
    <li>IDC &mdash; Worldwide Legal Tech Forecast (2025&ndash;2028)</li>
    <li>Goldman Sachs &mdash; Generative AI: Enterprise Adoption Rates (Jan 2026)</li>
    <li>Evaluetor Internal &mdash; Competitive Feature Comparison v3.0 (March 2026)</li>
    <li>Evaluetor Internal &mdash; Product Vision and Feature Roadmap (April 2026)</li>
    <li>Evaluetor Internal &mdash; Platform Architecture: 41 routers, ~315 API endpoints, 48 models, ~55 database tables, 9 AI agents, 30+ frontend pages</li>
  </ol>

  <div style="margin-top: 60px; border-top: 1px solid var(--border); padding-top: 20px;">
    <p style="font-size: 9pt; color: var(--text-muted); text-align: center;">&copy; 2026 Evaluetor Inc. All rights reserved.</p>
    <p style="font-size: 8pt; color: var(--text-muted); text-align: center;">CONFIDENTIAL &mdash; For Authorized Recipients Only | April 2026</p>
  </div>
</div>

</body>
</html>
"""


def main():
    output_path = "docs/Evaluetor_Business_Plan_2026.pdf"
    print("Generating PDF...")
    html = weasyprint.HTML(string=HTML_CONTENT)
    html.write_pdf(output_path)
    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
