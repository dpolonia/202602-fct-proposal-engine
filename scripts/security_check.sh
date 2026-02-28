#!/usr/bin/env bash
# =============================================================================
# scripts/security_check.sh — Pre-commit security gate
#
# Run by Claude Code before every commit. Exits non-zero if any check fails.
# Designed to be fast (<10s) and catch the most common security mistakes.
#
# Usage:
#   bash scripts/security_check.sh              # check staged files only
#   bash scripts/security_check.sh --all        # check entire repo
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
YLW='\033[0;33m'
GRN='\033[0;32m'
RST='\033[0m'

BLOCKERS=0
WARNINGS=0

blocker() { echo -e "${RED}🔴 BLOCKER:${RST} $1"; BLOCKERS=$((BLOCKERS + 1)); }
warning() { echo -e "${YLW}🟡 WARNING:${RST} $1"; WARNINGS=$((WARNINGS + 1)); }
pass()    { echo -e "${GRN}  ✓${RST} $1"; }

echo "═══════════════════════════════════════════════════════════"
echo " FCT Proposal Engine — Security Assessment"
echo " $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Determine scope
if [[ "${1:-}" == "--all" ]]; then
    FILES=$(find src/ tests/ scripts/ drafts/ data/ -type f \( -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.sh" -o -name "*.md" \) 2>/dev/null)
    SCOPE="full repo"
else
    FILES=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || echo "")
    SCOPE="staged files"
    if [[ -z "$FILES" ]]; then
        echo "No staged files to check. Use --all to check entire repo."
        exit 0
    fi
fi

echo "Scope: ${SCOPE}"
echo "Files: $(echo "$FILES" | wc -l | tr -d ' ')"
echo ""

# ─── 1. SECRETS & CREDENTIALS ───────────────────────────────────────────────
echo "── 1. Secrets & Credentials ──"

# 1a. API keys in source code
API_KEY_PATTERNS='(sk-ant-|sk-proj-|AIzaSy|ghp_|gho_|AKIA[0-9A-Z]|xoxb-|xoxp-|hf_[a-zA-Z0-9])'
HITS=$(echo "$FILES" | xargs grep -rPn "$API_KEY_PATTERNS" 2>/dev/null | grep -v '.env' | grep -v '.gitignore' | grep -v 'security_check\.sh' | grep -v 'sanitize\.py' | grep -v 'test_security\.py' | grep -v 'docs/' | grep -v 'tutorial' | grep -v '\.\.\.COLA' | grep -v 'sk-ant-\.\.\.' || true)
if [[ -n "$HITS" ]]; then
    blocker "Possible API keys/tokens found in source:"
    echo "$HITS" | head -10 | sed 's/^/         /'
else
    pass "No API keys detected in source files"
fi

# 1b. .env committed
ENV_STAGED=$(echo "$FILES" | grep -E '^\.env$|^\.env\.' | grep -v '\.env\.example' || true)
if [[ -n "$ENV_STAGED" ]]; then
    blocker ".env file is staged for commit — remove with: git reset HEAD .env"
else
    pass ".env not staged"
fi

# 1c. .env in .gitignore
if grep -q '^\.env' .gitignore 2>/dev/null; then
    pass ".env in .gitignore"
else
    blocker ".env NOT in .gitignore"
fi

# 1d. Hardcoded passwords/secrets in Python
SECRET_PATTERNS='(password|passwd|secret|token|api_key|apikey)\s*=\s*["\x27][^"\x27]{8,}'
PY_FILES=$(echo "$FILES" | grep '\.py$' || true)
if [[ -n "$PY_FILES" ]]; then
    HITS=$(echo "$PY_FILES" | xargs grep -rPni "$SECRET_PATTERNS" 2>/dev/null | grep -v 'os\.getenv\|os\.environ\|settings\.\|secrets\.\|\.env\|test_\|mock\|example\|placeholder\|TODO\|FIXME' || true)
    if [[ -n "$HITS" ]]; then
        blocker "Possible hardcoded secrets in Python:"
        echo "$HITS" | head -10 | sed 's/^/         /'
    else
        pass "No hardcoded secrets in Python source"
    fi
fi
echo ""

# ─── 2. SECRETS IN LOGS/OUTPUT ──────────────────────────────────────────────
echo "── 2. Secrets in Logs & Output ──"

if [[ -n "$PY_FILES" ]]; then
    # 2a. Logging API keys or secrets objects
    LOG_LEAKS=$(echo "$PY_FILES" | xargs grep -Pn '(logger?\.(debug|info|warning|error)|print)\(.*\b(api_key|secret|token|password|credential)\b' 2>/dev/null || true)
    if [[ -n "$LOG_LEAKS" ]]; then
        blocker "Possible secret values in log/print statements:"
        echo "$LOG_LEAKS" | head -10 | sed 's/^/         /'
    else
        pass "No secrets found in log/print statements"
    fi

    # 2b. f-string or format with secrets
    FSTR_LEAKS=$(echo "$PY_FILES" | xargs grep -Pn 'f["\x27].*\{.*\b(api_key|secret|token|password)\b.*\}' 2>/dev/null | grep -v 'mask\|redact\|***\|has_key' || true)
    if [[ -n "$FSTR_LEAKS" ]]; then
        warning "Possible secrets in f-strings (verify masking):"
        echo "$FSTR_LEAKS" | head -10 | sed 's/^/         /'
    else
        pass "No unmasked secrets in f-strings"
    fi
fi
echo ""

# ─── 3. ARCHITECTURE CONFORMANCE ────────────────────────────────────────────
echo "── 3. Architecture Conformance ──"

if [[ -n "$PY_FILES" ]]; then
    # 3a. Direct provider instantiation (bypass factory)
    DIRECT=$(echo "$PY_FILES" | xargs grep -Pn '(AnthropicClient|OpenAIClient|GoogleClient|HuggingFaceClient)\(' 2>/dev/null | grep -v 'llm_client\.py\|test_' || true)
    if [[ -n "$DIRECT" ]]; then
        warning "Direct LLM client instantiation (should use get_llm_client factory):"
        echo "$DIRECT" | head -10 | sed 's/^/         /'
    else
        pass "All LLM access via factory pattern"
    fi

    # 3b. Hardcoded model names outside config/settings
    MODEL_HARDCODE=$(echo "$PY_FILES" | xargs grep -Pn '(claude-|gpt-|gemini-|llama-)' 2>/dev/null | grep -v 'config\|settings\|test_\|comment\|#\|CLAUDE\.md\|GEMINI\.md\|README' || true)
    if [[ -n "$MODEL_HARDCODE" ]]; then
        warning "Hardcoded model names outside config layer:"
        echo "$MODEL_HARDCODE" | head -10 | sed 's/^/         /'
    else
        pass "No hardcoded model names in business logic"
    fi

    # 3c. Direct os.environ for secrets (should use secrets object)
    DIRECT_ENV=$(echo "$PY_FILES" | xargs grep -Pn 'os\.(environ|getenv)\(.*(_KEY|_SECRET|_TOKEN)' 2>/dev/null | grep -v 'settings\.py\|test_' || true)
    if [[ -n "$DIRECT_ENV" ]]; then
        warning "Direct os.environ for secrets (should use secrets object from settings.py):"
        echo "$DIRECT_ENV" | head -10 | sed 's/^/         /'
    else
        pass "Secrets accessed via settings.py only"
    fi
fi
echo ""

# ─── 4. INPUT VALIDATION ────────────────────────────────────────────────────
echo "── 4. Input Validation ──"

if [[ -n "$PY_FILES" ]]; then
    # 4a. YAML loading without safe_load
    UNSAFE_YAML=$(echo "$PY_FILES" | xargs grep -Pn 'yaml\.load\(' 2>/dev/null | grep -v 'safe_load\|Loader=yaml\.SafeLoader' || true)
    if [[ -n "$UNSAFE_YAML" ]]; then
        blocker "Unsafe YAML loading (use yaml.safe_load or Loader=SafeLoader):"
        echo "$UNSAFE_YAML" | head -10 | sed 's/^/         /'
    else
        pass "All YAML loading is safe"
    fi

    # 4b. eval/exec usage
    EVAL_USE=$(echo "$PY_FILES" | xargs grep -Pn '\b(eval|exec)\s*\(' 2>/dev/null | grep -v '#.*eval\|test_' || true)
    if [[ -n "$EVAL_USE" ]]; then
        blocker "eval/exec usage found (potential code injection):"
        echo "$EVAL_USE" | head -10 | sed 's/^/         /'
    else
        pass "No eval/exec usage"
    fi

    # 4c. Shell injection via subprocess
    SHELL_INJ=$(echo "$PY_FILES" | xargs grep -Pn 'subprocess\.(call|run|Popen)\(.*shell\s*=\s*True' 2>/dev/null || true)
    if [[ -n "$SHELL_INJ" ]]; then
        warning "subprocess with shell=True (verify input sanitisation):"
        echo "$SHELL_INJ" | head -10 | sed 's/^/         /'
    else
        pass "No shell=True subprocess calls"
    fi

    # 4d. Path traversal
    PATH_TRAV=$(echo "$PY_FILES" | xargs grep -Pn 'open\(.*\+.*\)' 2>/dev/null | grep -v 'test_\|os\.path\.join' || true)
    if [[ -n "$PATH_TRAV" ]]; then
        warning "String concatenation in file open (consider os.path.join / pathlib):"
        echo "$PATH_TRAV" | head -5 | sed 's/^/         /'
    else
        pass "No obvious path traversal risks"
    fi
fi
echo ""

# ─── 5. DEPENDENCY SAFETY ───────────────────────────────────────────────────
echo "── 5. Dependency Safety ──"

# 5a. Requirements pinning
if [[ -f "pyproject.toml" ]]; then
    UNPINNED=$(grep -P '^\s*"[a-zA-Z].*[^=]",$' pyproject.toml 2>/dev/null | grep -v '>=' | grep -v '==' | head -5 || true)
    if [[ -n "$UNPINNED" ]]; then
        warning "Some dependencies may not be pinned in pyproject.toml (verify):"
        echo "$UNPINNED" | sed 's/^/         /'
    else
        pass "Dependencies appear pinned"
    fi
fi

# 5b. requirements.txt with known issues
if [[ -f "requirements.txt" ]]; then
    warning "requirements.txt exists alongside pyproject.toml — ensure they are in sync"
fi

# 5c. pip-audit vulnerability scan
if command -v pip-audit &>/dev/null; then
    AUDIT_OUT=$(pip-audit --strict --progress-spinner=off 2>&1 || true)
    VULN_COUNT=$(echo "$AUDIT_OUT" | grep -c "^Name" || true)
    if echo "$AUDIT_OUT" | grep -q "found [1-9]"; then
        warning "pip-audit found known vulnerabilities:"
        echo "$AUDIT_OUT" | grep -v "^$" | head -15 | sed 's/^/         /'
    else
        pass "pip-audit: no known vulnerabilities"
    fi
else
    warning "pip-audit not installed (pip install pip-audit)"
fi
echo ""

# ─── 6. OUTPUT & DATA SAFETY ────────────────────────────────────────────────
echo "── 6. Output & Data Safety ──"

# 6a. Output directory in .gitignore
if grep -q '^output/' .gitignore 2>/dev/null; then
    pass "output/ in .gitignore"
else
    warning "output/ NOT in .gitignore — generated proposals may contain sensitive content"
fi

# 6b. PII patterns in YAML drafts
YAML_FILES=$(echo "$FILES" | grep -E '\.ya?ml$' || true)
if [[ -n "$YAML_FILES" ]]; then
    PII=$(echo "$YAML_FILES" | xargs grep -Pni '(\+351[\s.]?\d|nif:\s*\d|contribuinte|CC\s*\d{8}|BI\s*\d{8})' 2>/dev/null || true)
    if [[ -n "$PII" ]]; then
        blocker "Possible PII (phone/NIF/ID) in YAML files:"
        echo "$PII" | head -5 | sed 's/^/         /'
    else
        pass "No obvious PII in YAML files"
    fi
fi

# 6c. Logs directory in .gitignore
if grep -q '^logs/' .gitignore 2>/dev/null; then
    pass "logs/ in .gitignore"
else
    warning "logs/ NOT in .gitignore"
fi
echo ""

# ─── 7. NETWORK & API SAFETY ────────────────────────────────────────────────
echo "── 7. Network & API Safety ──"

if [[ -n "$PY_FILES" ]]; then
    # 7a. HTTP without TLS
    PLAIN_HTTP=$(echo "$PY_FILES" | xargs grep -Pn 'http://' 2>/dev/null | grep -v 'https\|localhost\|127\.0\.0\.1\|0\.0\.0\.0\|#\|comment' || true)
    if [[ -n "$PLAIN_HTTP" ]]; then
        warning "Plain HTTP URLs found (should use HTTPS):"
        echo "$PLAIN_HTTP" | head -5 | sed 's/^/         /'
    else
        pass "All external URLs use HTTPS"
    fi

    # 7b. verify=False in requests
    NO_VERIFY=$(echo "$PY_FILES" | xargs grep -Pn 'verify\s*=\s*False' 2>/dev/null || true)
    if [[ -n "$NO_VERIFY" ]]; then
        blocker "TLS verification disabled (verify=False):"
        echo "$NO_VERIFY" | head -5 | sed 's/^/         /'
    else
        pass "No TLS verification bypass"
    fi

    # 7c. Timeout on API calls
    NO_TIMEOUT=$(echo "$PY_FILES" | xargs grep -Pn '(requests\.(get|post|put)|httpx\.(get|post|put))' 2>/dev/null | grep -v 'timeout' || true)
    if [[ -n "$NO_TIMEOUT" ]]; then
        warning "HTTP calls without explicit timeout:"
        echo "$NO_TIMEOUT" | head -5 | sed 's/^/         /'
    else
        pass "HTTP calls have timeouts (or use SDK defaults)"
    fi
fi
echo ""

# ─── SUMMARY ────────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════"
echo " SUMMARY"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo -e " 🔴 Blockers:  ${BLOCKERS}"
echo -e " 🟡 Warnings:  ${WARNINGS}"
echo ""

if [[ $BLOCKERS -gt 0 ]]; then
    echo -e "${RED}❌ SECURITY GATE FAILED — fix all blockers before committing.${RST}"
    echo ""
    exit 1
else
    echo -e "${GRN}✅ SECURITY GATE PASSED — safe to commit.${RST}"
    echo ""
    exit 0
fi
