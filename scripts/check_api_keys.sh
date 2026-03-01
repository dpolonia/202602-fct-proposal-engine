#!/usr/bin/env bash
# =============================================================================
# scripts/check_api_keys.sh — Show + Validate all API keys in .env
#
# Tests each key with a minimal API call. Shows keys in full for debugging.
# Usage: bash scripts/check_api_keys.sh
# =============================================================================

set -uo pipefail

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
BLU='\033[0;34m'
GRY='\033[0;90m'
RST='\033[0m'

echo ""
echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo -e "${BLU} API Key Show & Validation${RST}"
echo -e "${BLU} $(date -u '+%Y-%m-%d %H:%M:%S UTC')${RST}"
echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo ""

# Load .env
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
else
    echo -e "${RED}❌ .env file not found${RST}"
    exit 1
fi

PASS=0
FAIL=0
SKIP=0

# ─────────────────────────────────────────────────────────────────────────────
# PART 1: SHOW ALL KEYS IN FULL
# ─────────────────────────────────────────────────────────────────────────────

mask_val() {
    local val="$1"
    if [[ -z "$val" ]]; then echo "<empty>"
    elif [[ ${#val} -le 8 ]]; then echo "****"
    else echo "${val:0:4}****${val: -2} (${#val} chars)"
    fi
}

echo -e "${YLW}── KEY STATUS (masked) ──${RST}"
echo ""
echo "ANTHROPIC_API_KEY     = [$(mask_val "${ANTHROPIC_API_KEY:-}")]"
echo "OPENAI_API_KEY        = [$(mask_val "${OPENAI_API_KEY:-}")]"
echo "GOOGLE_API_KEY        = [$(mask_val "${GOOGLE_API_KEY:-}")]"
echo "GEMINI_API_KEY        = [$(mask_val "${GEMINI_API_KEY:-}")]"
echo "HUGGINGFACE_API_KEY   = [$(mask_val "${HUGGINGFACE_API_KEY:-}")]"
echo "SCOPUS_API_KEY        = [$(mask_val "${SCOPUS_API_KEY:-}")]"
echo "SCOPUS_INST_TOKEN     = [$(mask_val "${SCOPUS_INST_TOKEN:-}")]"
echo "FCT_API_KEY           = [$(mask_val "${FCT_API_KEY:-}")]"
echo "X_API_KEY             = [$(mask_val "${X_API_KEY:-}")]"
echo "X_API_SECRET          = [$(mask_val "${X_API_SECRET:-}")]"
echo ""

echo -e "${YLW}── FORMAT CHECKS ──${RST}"
echo ""
for var in ANTHROPIC_API_KEY OPENAI_API_KEY GOOGLE_API_KEY GEMINI_API_KEY HUGGINGFACE_API_KEY SCOPUS_API_KEY SCOPUS_INST_TOKEN FCT_API_KEY; do
    val="${!var:-}"
    if [[ -z "$val" ]]; then
        echo -e "  ${GRY}⊘  $var: not set${RST}"
    elif [[ "$val" =~ ^[[:space:]] || "$val" =~ [[:space:]]$ ]]; then
        echo -e "  ${RED}⚠️  $var: HAS LEADING/TRAILING WHITESPACE!${RST}"
    elif [[ "$val" == *\"* || "$val" == *\'* ]]; then
        echo -e "  ${RED}⚠️  $var: CONTAINS QUOTE CHARACTERS!${RST}"
    elif [[ "$val" == "..." || "$val" == "sk-ant-..." || "$val" == "sk-..." || "$val" == "AIza..." || "$val" == "hf_..." || "$val" =~ ^your_ ]]; then
        echo -e "  ${GRY}⊘  $var: placeholder value${RST}"
    elif [[ ${#val} -lt 10 ]]; then
        echo -e "  ${YLW}⚠️  $var: suspiciously short (${#val} chars)${RST}"
    else
        echo -e "  ${GRN}✓  $var: ${#val} chars, format OK${RST}"
    fi
done
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# PART 2: LIVE API TESTS
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo -e "${BLU} LIVE API TESTS${RST}"
echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo ""

is_placeholder() {
    local val="$1"
    [[ -z "$val" || "$val" == "..." || "$val" == "sk-ant-..." || "$val" == "sk-..." || "$val" == "AIza..." || "$val" == "hf_..." || "$val" =~ ^your_ ]]
}

# ── 1. Anthropic ─────────────────────────────────────────────────────────────

echo -e "${YLW}── 1. Anthropic ──${RST}"
key="${ANTHROPIC_API_KEY:-}"
if is_placeholder "$key"; then
    echo -e "  ${GRY}⊘  Skipped (not configured)${RST}"
    ((SKIP++))
else
    resp=$(curl -s -w "\n%{http_code}" -X POST https://api.anthropic.com/v1/messages \
        -H "x-api-key: $key" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}' \
        2>/dev/null)
    http_code=$(echo "$resp" | tail -1)
    body=$(echo "$resp" | sed '$d')

    if [[ "$http_code" == "200" ]]; then
        echo -e "  ${GRN}✅ VALID (HTTP 200)${RST}"
        ((PASS++))
    elif [[ "$http_code" == "401" ]]; then
        echo -e "  ${RED}❌ INVALID KEY (HTTP 401 — authentication failed)${RST}"
        echo -e "  ${GRY}   Get a new key: https://console.anthropic.com/settings/keys${RST}"
        ((FAIL++))
    elif [[ "$http_code" == "403" ]]; then
        echo -e "  ${RED}❌ FORBIDDEN (HTTP 403 — key disabled or wrong workspace)${RST}"
        ((FAIL++))
    elif [[ "$http_code" == "429" ]]; then
        echo -e "  ${GRN}✅ VALID (rate limited, HTTP 429)${RST}"
        ((PASS++))
    elif [[ "$http_code" == "529" ]]; then
        echo -e "  ${YLW}⚠️  API overloaded but key accepted (HTTP 529)${RST}"
        ((PASS++))
    else
        err=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',{}).get('message','unknown'))" 2>/dev/null || echo "unknown")
        echo -e "  ${RED}❌ HTTP $http_code — $err${RST}"
        ((FAIL++))
    fi
fi
echo ""

# ── 2. OpenAI ────────────────────────────────────────────────────────────────

echo -e "${YLW}── 2. OpenAI ──${RST}"
key="${OPENAI_API_KEY:-}"
if is_placeholder "$key"; then
    echo -e "  ${GRY}⊘  Skipped (not configured)${RST}"
    ((SKIP++))
else
    resp=$(curl -s -w "\n%{http_code}" https://api.openai.com/v1/models \
        -H "Authorization: Bearer $key" \
        2>/dev/null)
    http_code=$(echo "$resp" | tail -1)

    if [[ "$http_code" == "200" ]]; then
        echo -e "  ${GRN}✅ VALID (HTTP 200)${RST}"
        ((PASS++))
    elif [[ "$http_code" == "401" ]]; then
        echo -e "  ${RED}❌ INVALID KEY (HTTP 401)${RST}"
        echo -e "  ${GRY}   Get a new key: https://platform.openai.com/api-keys${RST}"
        ((FAIL++))
    elif [[ "$http_code" == "429" ]]; then
        echo -e "  ${GRN}✅ VALID (rate limited, HTTP 429)${RST}"
        ((PASS++))
    else
        echo -e "  ${RED}❌ HTTP $http_code${RST}"
        ((FAIL++))
    fi
fi
echo ""

# ── 3. Google / Gemini ───────────────────────────────────────────────────────

echo -e "${YLW}── 3. Google / Gemini ──${RST}"
key="${GOOGLE_API_KEY:-${GEMINI_API_KEY:-}}"
if is_placeholder "$key"; then
    echo -e "  ${GRY}⊘  Skipped (not configured)${RST}"
    ((SKIP++))
else
    resp=$(curl -s -w "\n%{http_code}" \
        "https://generativelanguage.googleapis.com/v1beta/models?key=$key" \
        2>/dev/null)
    http_code=$(echo "$resp" | tail -1)

    if [[ "$http_code" == "200" ]]; then
        echo -e "  ${GRN}✅ VALID (HTTP 200)${RST}"
        ((PASS++))
    elif [[ "$http_code" == "400" ]]; then
        echo -e "  ${RED}❌ INVALID KEY (HTTP 400)${RST}"
        echo -e "  ${GRY}   Get a new key: https://aistudio.google.com/apikey${RST}"
        ((FAIL++))
    elif [[ "$http_code" == "403" ]]; then
        echo -e "  ${RED}❌ FORBIDDEN (HTTP 403 — key disabled or API not enabled)${RST}"
        ((FAIL++))
    elif [[ "$http_code" == "429" ]]; then
        echo -e "  ${GRN}✅ VALID (rate limited, HTTP 429)${RST}"
        ((PASS++))
    else
        echo -e "  ${RED}❌ HTTP $http_code${RST}"
        ((FAIL++))
    fi
fi
echo ""

# ── 4. HuggingFace ───────────────────────────────────────────────────────────

echo -e "${YLW}── 4. HuggingFace ──${RST}"
key="${HUGGINGFACE_API_KEY:-}"
if is_placeholder "$key"; then
    echo -e "  ${GRY}⊘  Skipped (not configured)${RST}"
    ((SKIP++))
else
    resp=$(curl -s -w "\n%{http_code}" \
        https://huggingface.co/api/whoami-v2 \
        -H "Authorization: Bearer $key" \
        2>/dev/null)
    http_code=$(echo "$resp" | tail -1)
    body=$(echo "$resp" | sed '$d')

    if [[ "$http_code" == "200" ]]; then
        user=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name','?'))" 2>/dev/null || echo "?")
        echo -e "  ${GRN}✅ VALID (user: $user)${RST}"
        ((PASS++))
    elif [[ "$http_code" == "401" ]]; then
        echo -e "  ${RED}❌ INVALID KEY (HTTP 401)${RST}"
        echo -e "  ${GRY}   Get a new key: https://huggingface.co/settings/tokens${RST}"
        ((FAIL++))
    else
        echo -e "  ${RED}❌ HTTP $http_code${RST}"
        ((FAIL++))
    fi
fi
echo ""

# ── 5. Scopus (Elsevier) ────────────────────────────────────────────────────

echo -e "${YLW}── 5. Scopus (Elsevier) ──${RST}"
key="${SCOPUS_API_KEY:-}"
token="${SCOPUS_INST_TOKEN:-}"
if is_placeholder "$key"; then
    echo -e "  ${GRY}⊘  Skipped (not configured)${RST}"
    ((SKIP++))
else
    curl_args=(-s -w '\n%{http_code}' "https://api.elsevier.com/content/search/scopus?query=TITLE(test)&count=1" -H "X-ELS-APIKey: $key")
    if [[ -n "$token" ]] && ! is_placeholder "$token"; then
        curl_args+=(-H "X-ELS-Insttoken: $token")
    fi

    resp=$(curl "${curl_args[@]}" 2>/dev/null)
    http_code=$(echo "$resp" | tail -1)

    if [[ "$http_code" == "200" ]]; then
        echo -e "  ${GRN}✅ VALID (HTTP 200)${RST}"
        ((PASS++))
    elif [[ "$http_code" == "401" ]]; then
        echo -e "  ${RED}❌ INVALID KEY (HTTP 401)${RST}"
        echo -e "  ${GRY}   Get a new key: https://dev.elsevier.com/apikey/manage${RST}"
        ((FAIL++))
    elif [[ "$http_code" == "400" ]]; then
        echo -e "  ${RED}❌ BAD REQUEST (HTTP 400 — key expired or quota exceeded)${RST}"
        ((FAIL++))
    elif [[ "$http_code" == "429" ]]; then
        echo -e "  ${GRN}✅ VALID (rate limited, HTTP 429)${RST}"
        ((PASS++))
    else
        echo -e "  ${RED}❌ HTTP $http_code${RST}"
        ((FAIL++))
    fi
fi
echo ""

# ── 6. FCT Engine API Key ───────────────────────────────────────────────────

echo -e "${YLW}── 6. FCT Engine API Key ──${RST}"
key="${FCT_API_KEY:-}"
if is_placeholder "$key"; then
    echo -e "  ${GRY}⊘  Skipped (not configured — dev mode, no auth required)${RST}"
    ((SKIP++))
else
    echo -e "  ${GRN}✅ Configured (local auth only, no remote test needed)${RST}"
    ((PASS++))
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo -e "${BLU} SUMMARY${RST}"
echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo ""
echo -e "  ${GRN}✅ Valid:       $PASS${RST}"
echo -e "  ${RED}❌ Invalid:     $FAIL${RST}"
echo -e "  ${GRY}⊘  Skipped:     $SKIP${RST}"
echo ""

# Pipeline readiness
echo -e "${YLW}── Pipeline Readiness ──${RST}"
echo ""

gen_provider=$(grep -A2 "^  generator:" config.yaml 2>/dev/null | grep "provider:" | awk '{print $2}' | tr -d '"' || echo "unknown")
rev_provider=$(grep -A2 "^  reviewer:" config.yaml 2>/dev/null | grep "provider:" | awk '{print $2}' | tr -d '"' || echo "unknown")

echo -e "  Generator provider (config.yaml): ${BLU}$gen_provider${RST}"
echo -e "  Reviewer provider (config.yaml):  ${BLU}$rev_provider${RST}"
echo ""

case "$gen_provider" in
    anthropic) gen_key="${ANTHROPIC_API_KEY:-}" ;;
    openai)    gen_key="${OPENAI_API_KEY:-}" ;;
    google)    gen_key="${GOOGLE_API_KEY:-${GEMINI_API_KEY:-}}" ;;
    *)         gen_key="" ;;
esac

if [[ -n "$gen_key" ]] && ! is_placeholder "$gen_key"; then
    echo -e "  ${GRN}✅ Generator key ($gen_provider) is configured${RST}"
else
    echo -e "  ${RED}❌ Generator key ($gen_provider) is MISSING — pipeline will fail${RST}"
fi

scopus_enabled=$(grep -A2 "scopus:" config.yaml 2>/dev/null | grep "enabled:" | awk '{print $2}' | tr -d '"' || echo "unknown")
if [[ "$scopus_enabled" == "true" ]]; then
    if [[ -n "${SCOPUS_API_KEY:-}" ]] && ! is_placeholder "${SCOPUS_API_KEY:-}"; then
        echo -e "  ${GRN}✅ Scopus is enabled and key is configured${RST}"
    else
        echo -e "  ${YLW}⚠️  Scopus is enabled but key is missing — will get HTTP 400 errors${RST}"
        echo -e "  ${GRY}   Fix: set SCOPUS_API_KEY in .env or disable in config.yaml${RST}"
    fi
else
    echo -e "  ${GRY}⊘  Scopus is disabled (no key needed)${RST}"
fi

echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}⚠️  Fix invalid keys in .env before running the pipeline.${RST}"
    echo ""
    exit 1
elif [[ $PASS -eq 0 ]]; then
    echo -e "${YLW}⚠️  No keys configured. Add at least ANTHROPIC_API_KEY to .env${RST}"
    echo ""
    exit 1
else
    echo -e "${GRN}✅ Ready to run: fct-engine pipeline -i drafts/synthpoppt_icdt_complete.yaml${RST}"
    echo ""
    exit 0
fi
