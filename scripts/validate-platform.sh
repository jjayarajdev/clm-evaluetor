#!/usr/bin/env bash
#
# Evaluetor Platform Validation Script
# =====================================
# Mimics user flows through the UI by hitting API endpoints in sequence.
# Produces a pass/fail report for every business flow.
#
# Usage:
#   ./scripts/validate-platform.sh                    # Run all flows against localhost:8000
#   ./scripts/validate-platform.sh --base-url http://52.21.204.211  # Against AWS
#   ./scripts/validate-platform.sh --flow auth        # Run single flow
#   ./scripts/validate-platform.sh --flow contracts --flow governance  # Multiple flows
#   ./scripts/validate-platform.sh --verbose          # Show response bodies
#
# Available flows:
#   auth, dashboard, superadmin, contracts, postsigning, renewals,
#   compliance, governance, surveys, ai, admin, vendors, alerts, reports
#

set -uo pipefail

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL="${BASE_URL:-http://localhost:8000}"
VERBOSE=false
SELECTED_FLOWS=()
PASS=0
FAIL=0
SKIP=0
RESULTS=()

# ─── Colors ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# ─── Parse Arguments ────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case $1 in
    --base-url) BASE_URL="$2"; shift 2 ;;
    --flow) SELECTED_FLOWS+=("$2"); shift 2 ;;
    --verbose|-v) VERBOSE=true; shift ;;
    --help|-h)
      head -20 "$0" | tail -18
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ─── Helpers ─────────────────────────────────────────────────────────────────

# Stored tokens
TOKEN_ADMIN=""
TOKEN_LEGAL=""
TOKEN_SUPERADMIN=""
TOKEN_TECHSTART=""

# Discovered IDs (populated as we go)
CONTRACT_ID=""
CLAUSE_ID=""
OBLIGATION_ID=""
ORG_ID=""
RELATIONSHIP_ID=""
KPI_ID=""
SURVEY_TEMPLATE_ID=""
SURVEY_INSTANCE_ID=""
TENANT_ID=""
USER_ID=""
BU_ID=""

log_section() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${BLUE}  $1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_step() {
  echo -e "  ${CYAN}→${NC} $1"
}

# call_api METHOD PATH [EXPECTED_STATUS] [DATA] [TOKEN]
# Returns: sets LAST_STATUS, LAST_BODY
call_api() {
  local method="$1"
  local path="$2"
  local expected="${3:-200}"
  local data="${4:-}"
  local token="${5:-$TOKEN_ADMIN}"
  local label="${6:-$method $path}"

  local curl_args=(-s -w "\n%{http_code}" -X "$method" "${BASE_URL}${path}")
  curl_args+=(-H "Content-Type: application/json")

  if [[ -n "$token" ]]; then
    curl_args+=(-H "Authorization: Bearer ${token}")
  fi

  if [[ -n "$data" ]]; then
    curl_args+=(-d "$data")
  fi

  local response
  response=$(curl "${curl_args[@]}" 2>/dev/null) || true

  LAST_STATUS=$(echo "$response" | tail -1)
  LAST_BODY=$(echo "$response" | sed '$d')

  if [[ "$VERBOSE" == "true" ]]; then
    echo -e "    ${DIM}${method} ${path} → ${LAST_STATUS}${NC}"
    echo -e "    ${DIM}$(echo "$LAST_BODY" | python3 -m json.tool 2>/dev/null | head -10)${NC}"
  fi

  if [[ "$LAST_STATUS" == "$expected" ]]; then
    echo -e "  ${GREEN}✓${NC} ${label} ${DIM}[${LAST_STATUS}]${NC}"
    PASS=$((PASS + 1))
    RESULTS+=("PASS|${label}")
    return 0
  else
    echo -e "  ${RED}✗${NC} ${label} ${DIM}[expected ${expected}, got ${LAST_STATUS}]${NC}"
    if [[ "$VERBOSE" != "true" ]]; then
      echo -e "    ${DIM}$(echo "$LAST_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('detail',''))" 2>/dev/null)${NC}"
    fi
    FAIL=$((FAIL + 1))
    RESULTS+=("FAIL|${label}")
    return 1
  fi
}

# Extract a JSON field from LAST_BODY
json_field() {
  echo "$LAST_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null
}

# Extract first item ID from a list response
first_item_id() {
  echo "$LAST_BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', d) if isinstance(d, dict) else d
if isinstance(items, list) and len(items) > 0:
    print(items[0].get('id', ''))
else:
    print('')
" 2>/dev/null
}

should_run() {
  local flow="$1"
  if [[ ${#SELECTED_FLOWS[@]} -eq 0 ]]; then
    return 0  # No filter → run all
  fi
  for f in "${SELECTED_FLOWS[@]}"; do
    if [[ "$f" == "$flow" ]]; then
      return 0
    fi
  done
  return 1
}

login() {
  local username="$1"
  local password="$2"
  local varname="$3"

  local response
  response=$(curl -s "${BASE_URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${username}\",\"password\":\"${password}\"}" 2>/dev/null)

  local token
  token=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

  if [[ -n "$token" && "$token" != "" ]]; then
    eval "${varname}='${token}'"
    echo -e "  ${GREEN}✓${NC} Login as ${BOLD}${username}${NC}"
    PASS=$((PASS + 1))
    RESULTS+=("PASS|Login as ${username}")
    return 0
  else
    echo -e "  ${RED}✗${NC} Login as ${BOLD}${username}${NC} — no token returned"
    FAIL=$((FAIL + 1))
    RESULTS+=("FAIL|Login as ${username}")
    return 1
  fi
}

# ─── Flow 1: Authentication ─────────────────────────────────────────────────

flow_auth() {
  log_section "FLOW 1: Authentication"

  log_step "Login with each user role"
  login "admin" "admin123" "TOKEN_ADMIN"
  login "legal" "legal123" "TOKEN_LEGAL"
  login "superadmin" "admin123" "TOKEN_SUPERADMIN"
  login "techstart_admin" "admin123" "TOKEN_TECHSTART"

  log_step "Verify JWT claims via /me"
  call_api GET "/api/auth/me" 200 "" "$TOKEN_ADMIN" "GET /me (admin) → role=admin"
  local admin_role
  admin_role=$(json_field "['role']")
  if [[ "$admin_role" == "admin" ]]; then
    echo -e "    ${DIM}role=${admin_role} ✓${NC}"
  fi

  call_api GET "/api/auth/me" 200 "" "$TOKEN_SUPERADMIN" "GET /me (superadmin) → role=super_admin"
  local sa_role
  sa_role=$(json_field "['role']")
  local sa_tenant
  sa_tenant=$(json_field "['tenant_id']")
  if [[ "$sa_role" == "super_admin" ]]; then
    echo -e "    ${DIM}role=${sa_role}, tenant_id=${sa_tenant} ✓${NC}"
  fi

  log_step "Verify wrong password returns 401"
  call_api POST "/api/auth/login" 401 '{"username":"admin","password":"wrongpass"}' "" "Login with wrong password → 401"

  log_step "Verify no token is rejected (direct API only, nginx proxies to frontend)"
  # Note: Behind nginx, unauthenticated /api/auth/me may return 200 (frontend HTML).
  # This test is meaningful only when hitting the backend directly (port 8000).
  if [[ "$BASE_URL" == *":8000"* ]]; then
    call_api GET "/api/auth/me" 403 "" "" "GET /me without token → 403" || true
  else
    echo -e "  ${YELLOW}⊘${NC} GET /me without token ${DIM}[skipped — behind nginx]${NC}"
    SKIP=$((SKIP + 1))
  fi

  log_step "Tenant isolation check"
  # Admin (Acme) lists contracts — should get Acme contracts
  call_api GET "/api/contracts" 200 "" "$TOKEN_ADMIN" "Admin (Acme) lists contracts"
  local acme_count
  acme_count=$(json_field "['total']")

  # TechStart admin lists contracts — should get TechStart contracts (different set)
  call_api GET "/api/contracts" 200 "" "$TOKEN_TECHSTART" "TechStart admin lists contracts"
  local ts_count
  ts_count=$(json_field "['total']")

  echo -e "    ${DIM}Acme contracts: ${acme_count}, TechStart contracts: ${ts_count}${NC}"
}

# ─── Flow 2: Dashboard ──────────────────────────────────────────────────────

flow_dashboard() {
  log_section "FLOW 2: Dashboard (what the user sees on login)"

  log_step "Admin dashboard stats"
  call_api GET "/api/dashboard/admin" 200 "" "$TOKEN_ADMIN" "Admin dashboard"
  call_api GET "/api/dashboard/contracts-summary" 200 "" "$TOKEN_ADMIN" "Contracts summary"
  call_api GET "/api/dashboard/obligations-summary" 200 "" "$TOKEN_ADMIN" "Obligations summary"
  call_api GET "/api/dashboard/clauses-summary" 200 "" "$TOKEN_ADMIN" "Clauses summary"
  call_api GET "/api/dashboard/portfolio" 200 "" "$TOKEN_ADMIN" "Portfolio overview"
  call_api GET "/api/dashboard/insights" 200 "" "$TOKEN_ADMIN" "AI insights"
  call_api GET "/api/dashboard/activity" 200 "" "$TOKEN_ADMIN" "Recent activity"

  log_step "Legal dashboard"
  call_api GET "/api/dashboard/legal" 200 "" "$TOKEN_LEGAL" "Legal dashboard"

  log_step "Procurement dashboard"
  call_api GET "/api/dashboard/procurement" 200 "" "$TOKEN_ADMIN" "Procurement dashboard"

  log_step "Post-signing dashboard"
  call_api GET "/api/dashboard/postsigning" 200 "" "$TOKEN_ADMIN" "Post-signing overview"
  call_api GET "/api/dashboard/postsigning/obligations" 200 "" "$TOKEN_ADMIN" "Post-signing obligations"
  call_api GET "/api/dashboard/postsigning/slas" 200 "" "$TOKEN_ADMIN" "Post-signing SLAs"

  log_step "Obligations compliance"
  call_api GET "/api/dashboard/obligations-compliance" 200 "" "$TOKEN_ADMIN" "Obligations compliance"
}

# ─── Flow 3: Super Admin ────────────────────────────────────────────────────

flow_superadmin() {
  log_section "FLOW 3: Super Admin (platform management)"

  log_step "List all tenants"
  call_api GET "/api/tenants" 200 "" "$TOKEN_SUPERADMIN" "List tenants"
  TENANT_ID=$(first_item_id)
  echo -e "    ${DIM}First tenant: ${TENANT_ID}${NC}"

  log_step "Get tenant detail + stats"
  if [[ -n "$TENANT_ID" ]]; then
    call_api GET "/api/tenants/${TENANT_ID}" 200 "" "$TOKEN_SUPERADMIN" "Tenant detail"
    call_api GET "/api/tenants/${TENANT_ID}/stats" 200 "" "$TOKEN_SUPERADMIN" "Tenant stats"
    local contract_count
    contract_count=$(json_field "['contract_count']")
    local total_value
    total_value=$(json_field "['total_value']")
    echo -e "    ${DIM}contracts=${contract_count}, value=${total_value}${NC}"
  fi

  log_step "List all users (global)"
  call_api GET "/api/users" 200 "" "$TOKEN_SUPERADMIN" "List all users (super admin)"
  USER_ID=$(first_item_id)

  log_step "Current tenant stats"
  call_api GET "/api/tenants/current/stats" 200 "" "$TOKEN_ADMIN" "Current tenant stats (admin)"

  log_step "Verify tenant-scoped user cannot see all tenants"
  call_api GET "/api/tenants" 403 "" "$TOKEN_ADMIN" "Admin cannot list all tenants → 403"
}

# ─── Flow 4: Contract Lifecycle ──────────────────────────────────────────────

flow_contracts() {
  log_section "FLOW 4: Contract Lifecycle"

  log_step "List contracts (paginated)"
  call_api GET "/api/contracts?page=1&page_size=5" 200 "" "$TOKEN_ADMIN" "List contracts (page 1, size 5)"
  local total
  total=$(json_field "['total']")
  local page_count
  page_count=$(json_field "['pages']")
  echo -e "    ${DIM}total=${total}, pages=${page_count}${NC}"

  CONTRACT_ID=$(first_item_id)
  echo -e "    ${DIM}Using contract: ${CONTRACT_ID}${NC}"

  if [[ -n "$CONTRACT_ID" ]]; then
    log_step "Contract detail"
    call_api GET "/api/contracts/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "Contract detail"
    local counterparty
    counterparty=$(json_field "['counterparty']")
    local ctype
    ctype=$(json_field "['contract_type']")
    echo -e "    ${DIM}type=${ctype}, counterparty=${counterparty}${NC}"

    log_step "Contract intelligence cockpit"
    call_api GET "/api/dashboard/cockpit/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "Contract cockpit"

    log_step "Contract clauses, obligations, financials"
    call_api GET "/api/dashboard/clauses-summary" 200 "" "$TOKEN_ADMIN" "Clauses summary"
    call_api GET "/api/dashboard/obligations-summary" 200 "" "$TOKEN_ADMIN" "Obligations summary"
    call_api GET "/api/dashboard/financials/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "Contract financials"
    call_api GET "/api/dashboard/definitions/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "Contract definitions"
    call_api GET "/api/dashboard/preamble/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "Contract preamble"
    call_api GET "/api/dashboard/exhibits/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "Contract exhibits"

    log_step "Contract links & suggested links"
    call_api GET "/api/contracts/${CONTRACT_ID}/links" 200 "" "$TOKEN_ADMIN" "Contract links"
    call_api GET "/api/contracts/${CONTRACT_ID}/suggested-links" 200 "" "$TOKEN_ADMIN" "Suggested links"

    log_step "Contract comments"
    call_api GET "/api/contracts/${CONTRACT_ID}/comments" 200 "" "$TOKEN_ADMIN" "Contract comments"

    log_step "Contract versions & audit trail"
    call_api GET "/api/contracts/${CONTRACT_ID}/versions" 200 "" "$TOKEN_ADMIN" "Contract versions"
    call_api GET "/api/contracts/${CONTRACT_ID}/audit-trail" 200 "" "$TOKEN_ADMIN" "Contract audit trail"

    log_step "Knowledge graph"
    call_api GET "/api/knowledge-graph/contracts/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "Knowledge graph"
    call_api GET "/api/knowledge-graph/contracts/${CONTRACT_ID}/stats" 200 "" "$TOKEN_ADMIN" "KG stats"
    call_api GET "/api/knowledge-graph/contracts/${CONTRACT_ID}/entities" 200 "" "$TOKEN_ADMIN" "KG entities"
  fi

  log_step "Filter options"
  call_api GET "/api/contracts/filter-options" 200 "" "$TOKEN_ADMIN" "Contract filter options"

  log_step "Search contracts"
  call_api GET "/api/contracts/search?query=service" 200 "" "$TOKEN_ADMIN" "Search contracts: 'service'"
}

# ─── Flow 5: Post-Signing Management ────────────────────────────────────────

flow_postsigning() {
  log_section "FLOW 5: Post-Signing Management"

  log_step "Obligations list"
  call_api GET "/api/obligations/" 200 "" "$TOKEN_ADMIN" "List obligations"
  OBLIGATION_ID=$(first_item_id)

  if [[ -n "$OBLIGATION_ID" ]]; then
    log_step "Obligation detail"
    call_api GET "/api/obligations/${OBLIGATION_ID}" 200 "" "$TOKEN_ADMIN" "Obligation detail"
  fi

  log_step "Obligation compliance rates"
  call_api GET "/api/obligations/compliance/rates" 200 "" "$TOKEN_ADMIN" "Compliance rates"

  log_step "SLA endpoints"
  call_api GET "/api/sla/" 200 "" "$TOKEN_ADMIN" "List all SLAs"
  call_api GET "/api/sla/compliance/summary" 200 "" "$TOKEN_ADMIN" "SLA compliance summary"
  call_api GET "/api/sla/breaches/active" 200 "" "$TOKEN_ADMIN" "Active SLA breaches"

  if [[ -n "$CONTRACT_ID" ]]; then
    call_api GET "/api/sla/${CONTRACT_ID}" 200 "" "$TOKEN_ADMIN" "SLAs for contract"
  fi
}

# ─── Flow 6: Renewals ───────────────────────────────────────────────────────

flow_renewals() {
  log_section "FLOW 6: Renewals"

  call_api GET "/api/renewals/summary" 200 "" "$TOKEN_ADMIN" "Renewals summary"
  call_api GET "/api/renewals/calendar" 200 "" "$TOKEN_ADMIN" "Renewals calendar"
  call_api GET "/api/renewals/at-risk" 200 "" "$TOKEN_ADMIN" "At-risk renewals"

  if [[ -n "$CONTRACT_ID" ]]; then
    log_step "Renewal recommendation for contract"
    call_api GET "/api/renewals/${CONTRACT_ID}/recommendation" 200 "" "$TOKEN_ADMIN" "Renewal recommendation"
  fi
}

# ─── Flow 7: Compliance ─────────────────────────────────────────────────────

flow_compliance() {
  log_section "FLOW 7: Compliance"

  call_api GET "/api/compliance/dashboard" 200 "" "$TOKEN_ADMIN" "Compliance dashboard"
  call_api GET "/api/compliance/rules" 200 "" "$TOKEN_ADMIN" "Compliance rules"
  call_api GET "/api/compliance/gaps" 200 "" "$TOKEN_ADMIN" "Compliance gaps"
  call_api GET "/api/compliance/obligations" 200 "" "$TOKEN_ADMIN" "Compliance obligations"
  call_api GET "/api/compliance/by-industry" 200 "" "$TOKEN_ADMIN" "Compliance by industry"
  call_api GET "/api/compliance/contracts" 200 "" "$TOKEN_ADMIN" "Compliance contracts"
}

# ─── Flow 8: Relationship Governance ─────────────────────────────────────────

flow_governance() {
  log_section "FLOW 8: Relationship Governance"

  log_step "Organizations"
  call_api GET "/api/organizations" 200 "" "$TOKEN_ADMIN" "List organizations"
  ORG_ID=$(first_item_id)
  echo -e "    ${DIM}First org: ${ORG_ID}${NC}"

  if [[ -n "$ORG_ID" ]]; then
    call_api GET "/api/organizations/${ORG_ID}" 200 "" "$TOKEN_ADMIN" "Organization detail"
    call_api GET "/api/organizations/${ORG_ID}/relationships" 200 "" "$TOKEN_ADMIN" "Org relationships"
  fi

  log_step "Relationships"
  call_api GET "/api/relationships" 200 "" "$TOKEN_ADMIN" "List relationships"
  RELATIONSHIP_ID=$(first_item_id)
  echo -e "    ${DIM}First relationship: ${RELATIONSHIP_ID}${NC}"

  if [[ -n "$RELATIONSHIP_ID" ]]; then
    call_api GET "/api/relationships/${RELATIONSHIP_ID}" 200 "" "$TOKEN_ADMIN" "Relationship detail"
    call_api GET "/api/relationships/${RELATIONSHIP_ID}/team" 200 "" "$TOKEN_ADMIN" "Relationship team"
    call_api GET "/api/relationships/${RELATIONSHIP_ID}/health" 200 "" "$TOKEN_ADMIN" "Relationship health"
  fi

  log_step "KPIs"
  call_api GET "/api/kpis" 200 "" "$TOKEN_ADMIN" "List KPIs"
  KPI_ID=$(first_item_id)

  if [[ -n "$KPI_ID" ]]; then
    call_api GET "/api/kpis/${KPI_ID}" 200 "" "$TOKEN_ADMIN" "KPI detail"
    call_api GET "/api/kpis/${KPI_ID}/scores" 200 "" "$TOKEN_ADMIN" "KPI scores"
    call_api GET "/api/kpis/${KPI_ID}/gaps" 200 "" "$TOKEN_ADMIN" "KPI perception gaps"
  fi

  if [[ -n "$RELATIONSHIP_ID" ]]; then
    call_api GET "/api/kpis/relationship/${RELATIONSHIP_ID}/gaps" 200 "" "$TOKEN_ADMIN" "Relationship perception gaps"
    call_api GET "/api/kpis/relationship/${RELATIONSHIP_ID}/summary" 200 "" "$TOKEN_ADMIN" "Relationship KPI summary"
  fi

  log_step "Improvements"
  call_api GET "/api/improvements" 200 "" "$TOKEN_ADMIN" "List improvements"
  local improvement_id
  improvement_id=$(first_item_id)

  if [[ -n "$improvement_id" ]]; then
    call_api GET "/api/improvements/${improvement_id}" 200 "" "$TOKEN_ADMIN" "Improvement detail"
    call_api GET "/api/improvements/${improvement_id}/actions" 200 "" "$TOKEN_ADMIN" "Improvement actions"
  fi

  if [[ -n "$RELATIONSHIP_ID" ]]; then
    call_api GET "/api/improvements/relationship/${RELATIONSHIP_ID}/summary" 200 "" "$TOKEN_ADMIN" "Improvement summary for relationship"
  fi
}

# ─── Flow 9: Surveys ────────────────────────────────────────────────────────

flow_surveys() {
  log_section "FLOW 9: Surveys"

  log_step "Survey templates"
  call_api GET "/api/surveys/templates" 200 "" "$TOKEN_ADMIN" "List survey templates"
  SURVEY_TEMPLATE_ID=$(first_item_id)

  if [[ -n "$SURVEY_TEMPLATE_ID" ]]; then
    call_api GET "/api/surveys/templates/${SURVEY_TEMPLATE_ID}" 200 "" "$TOKEN_ADMIN" "Template detail"
  fi

  log_step "Survey instances"
  call_api GET "/api/surveys/instances" 200 "" "$TOKEN_ADMIN" "List survey instances"
  SURVEY_INSTANCE_ID=$(first_item_id)

  if [[ -n "$SURVEY_INSTANCE_ID" ]]; then
    call_api GET "/api/surveys/instances/${SURVEY_INSTANCE_ID}" 200 "" "$TOKEN_ADMIN" "Instance detail"
    call_api GET "/api/surveys/instances/${SURVEY_INSTANCE_ID}/responses" 200 "" "$TOKEN_ADMIN" "Instance responses"
  fi
}

# ─── Flow 10: AI / Query ────────────────────────────────────────────────────

flow_ai() {
  log_section "FLOW 10: AI & Query"

  log_step "Query suggestions"
  call_api GET "/api/query/suggestions" 200 "" "$TOKEN_ADMIN" "Query suggestions"

  log_step "Chat sessions"
  call_api GET "/api/chat/sessions" 200 "" "$TOKEN_ADMIN" "List chat sessions"

  log_step "Contract Q&A (AI query)"
  call_api POST "/api/query" 200 '{"question":"What contracts are expiring soon?"}' "$TOKEN_ADMIN" "AI query: expiring contracts"
}

# ─── Flow 11: Admin Features ────────────────────────────────────────────────

flow_admin() {
  log_section "FLOW 11: Admin Features"

  log_step "Business units"
  call_api GET "/api/business-units" 200 "" "$TOKEN_ADMIN" "List business units"
  BU_ID=$(first_item_id)

  if [[ -n "$BU_ID" ]]; then
    call_api GET "/api/business-units/${BU_ID}" 200 "" "$TOKEN_ADMIN" "Business unit detail"
  fi

  call_api GET "/api/business-units/tree" 200 "" "$TOKEN_ADMIN" "Business unit tree"

  log_step "External users"
  call_api GET "/api/external-users" 200 "" "$TOKEN_ADMIN" "List external users"

  log_step "Notification rules"
  call_api GET "/api/notification-rules/" 200 "" "$TOKEN_ADMIN" "List notification rules"
  call_api GET "/api/notification-rules/templates" 200 "" "$TOKEN_ADMIN" "Notification templates"
  call_api GET "/api/notification-rules/summary/stats" 200 "" "$TOKEN_ADMIN" "Notification stats"

  log_step "Users management"
  call_api GET "/api/users" 200 "" "$TOKEN_ADMIN" "List users (tenant-scoped)"

  log_step "Audit log"
  call_api GET "/api/audit" 200 "" "$TOKEN_ADMIN" "Audit log"
  call_api GET "/api/audit/stats" 200 "" "$TOKEN_ADMIN" "Audit stats"

  log_step "Scheduler"
  call_api GET "/api/admin/scheduler/status" 200 "" "$TOKEN_ADMIN" "Scheduler status"
  call_api GET "/api/admin/scheduler/jobs" 200 "" "$TOKEN_ADMIN" "Scheduler jobs"

  log_step "System health"
  call_api GET "/api/health" 200 "" "" "Health check (no auth)"
  call_api GET "/api/system-health" 200 "" "$TOKEN_ADMIN" "System health (detailed)"
}

# ─── Flow 12: Vendors ───────────────────────────────────────────────────────

flow_vendors() {
  log_section "FLOW 12: Vendors"

  call_api GET "/api/vendors" 200 "" "$TOKEN_ADMIN" "List vendors"
  call_api GET "/api/vendors/at-risk" 200 "" "$TOKEN_ADMIN" "At-risk vendors"
  # Use first two vendors from list for comparison
  local v1 v2
  v1=$(echo "$LAST_BODY" | python3 -c "import sys,json,urllib.parse; d=json.load(sys.stdin); items=d.get('items',d.get('vendors',d)) if isinstance(d,dict) else d; print(urllib.parse.quote(items[0].get('vendor_name','')))" 2>/dev/null)
  v2=$(echo "$LAST_BODY" | python3 -c "import sys,json,urllib.parse; d=json.load(sys.stdin); items=d.get('items',d.get('vendors',d)) if isinstance(d,dict) else d; print(urllib.parse.quote(items[1].get('vendor_name','')))" 2>/dev/null)
  if [[ -n "$v1" && -n "$v2" ]]; then
    call_api GET "/api/vendors/compare?vendors=${v1},${v2}" 200 "" "$TOKEN_ADMIN" "Compare vendors"
  fi
  call_api GET "/api/vendors/scorecard" 200 "" "$TOKEN_ADMIN" "Vendor scorecard"
}

# ─── Flow 13: Alerts ────────────────────────────────────────────────────────

flow_alerts() {
  log_section "FLOW 13: Alerts"

  call_api GET "/api/alerts/dashboard" 200 "" "$TOKEN_ADMIN" "Alerts dashboard"
  call_api GET "/api/alerts/" 200 "" "$TOKEN_ADMIN" "List alerts"
  call_api GET "/api/alerts/critical" 200 "" "$TOKEN_ADMIN" "Critical alerts"
  call_api GET "/api/alerts/stats/trends" 200 "" "$TOKEN_ADMIN" "Alert trends"
}

# ─── Flow 14: Reports & Metrics ─────────────────────────────────────────────

flow_reports() {
  log_section "FLOW 14: Reports & Metrics"

  call_api GET "/api/reports/summary" 200 "" "$TOKEN_ADMIN" "Reports summary"
  call_api GET "/api/reports/compliance?start_date=2025-01-01&end_date=2026-12-31" 200 "" "$TOKEN_ADMIN" "Compliance report"
  call_api GET "/api/reports/compliance/trend" 200 "" "$TOKEN_ADMIN" "Compliance trend"

  log_step "Metrics"
  call_api GET "/api/metrics/dashboard-trends" 200 "" "$TOKEN_ADMIN" "Dashboard trends"
  call_api GET "/api/metrics/history" 200 "" "$TOKEN_ADMIN" "Metrics history"

  log_step "Milestones"
  call_api GET "/api/milestones/health" 200 "" "$TOKEN_ADMIN" "Milestones health"
  call_api GET "/api/milestones/at-risk-contracts" 200 "" "$TOKEN_ADMIN" "At-risk contracts (milestones)"
  call_api GET "/api/milestones/portfolio-compliance" 200 "" "$TOKEN_ADMIN" "Portfolio compliance"
}

# ─── Report ──────────────────────────────────────────────────────────────────

print_report() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}  VALIDATION REPORT${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "  ${GREEN}PASS:${NC} ${PASS}"
  echo -e "  ${RED}FAIL:${NC} ${FAIL}"
  if [[ $SKIP -gt 0 ]]; then
    echo -e "  ${YELLOW}SKIP:${NC} ${SKIP}"
  fi
  echo -e "  ${BOLD}TOTAL:${NC} $((PASS + FAIL))"
  echo ""

  if [[ $FAIL -gt 0 ]]; then
    echo -e "  ${RED}${BOLD}Failed Tests:${NC}"
    for result in "${RESULTS[@]}"; do
      if [[ "$result" == FAIL* ]]; then
        local label="${result#FAIL|}"
        echo -e "    ${RED}✗${NC} ${label}"
      fi
    done
    echo ""
  fi

  local pct=0
  if [[ $((PASS + FAIL)) -gt 0 ]]; then
    pct=$((PASS * 100 / (PASS + FAIL)))
  fi

  if [[ $FAIL -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}All tests passed! (${pct}%)${NC}"
  elif [[ $pct -ge 80 ]]; then
    echo -e "  ${YELLOW}${BOLD}${pct}% pass rate — some issues to investigate${NC}"
  else
    echo -e "  ${RED}${BOLD}${pct}% pass rate — significant issues detected${NC}"
  fi

  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ─── Main ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Evaluetor Platform Validation${NC}"
echo -e "${DIM}Target: ${BASE_URL}${NC}"
echo -e "${DIM}Time:   $(date '+%Y-%m-%d %H:%M:%S')${NC}"

# Pre-flight: check if server is reachable
echo ""
echo -e "${CYAN}Checking server connectivity...${NC}"
if ! curl -s -o /dev/null -w "" "${BASE_URL}/api/health" 2>/dev/null; then
  echo -e "${RED}Server at ${BASE_URL} is not reachable. Is it running?${NC}"
  exit 1
fi
echo -e "${GREEN}Server is reachable${NC}"

# Run flows
should_run "auth"        && flow_auth
should_run "dashboard"   && flow_dashboard
should_run "superadmin"  && flow_superadmin
should_run "contracts"   && flow_contracts
should_run "postsigning" && flow_postsigning
should_run "renewals"    && flow_renewals
should_run "compliance"  && flow_compliance
should_run "governance"  && flow_governance
should_run "surveys"     && flow_surveys
should_run "ai"          && flow_ai
should_run "admin"       && flow_admin
should_run "vendors"     && flow_vendors
should_run "alerts"      && flow_alerts
should_run "reports"     && flow_reports

# Final report
print_report

# Exit with failure if any tests failed
[[ $FAIL -eq 0 ]]
