#!/usr/bin/env bash
# =============================================================================
# scripts/gemini_review.sh — Automated Gemini code & security audit
#
# Usage:
#   bash scripts/gemini_review.sh              # review changes since last audit
#   bash scripts/gemini_review.sh --full       # full codebase audit
#   bash scripts/gemini_review.sh --security   # security-focused audit only
#   bash scripts/gemini_review.sh --pre-push   # combined gate before git push
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
BLU='\033[0;34m'
RST='\033[0m'

MARKER_FILE=".gemini/last_review_commit"
REPORT_FILE="audit_report.md"
MODE="${1:---changes}"

echo ""
echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo -e "${BLU} Gemini Code & Security Audit${RST}"
echo -e "${BLU} $(date -u '+%Y-%m-%d %H:%M:%S UTC')${RST}"
echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo ""

# ─── Phase 1: Security gate ─────────────────────────────────────────────────
echo -e "${YLW}── Phase 1: Security Gate ──${RST}"
if ! bash scripts/security_check.sh --all; then
    echo -e "${RED}❌ Security gate failed. Fix blockers before Gemini review.${RST}"
    exit 1
fi
echo -e "${GRN}✅ Security gate passed.${RST}"
echo ""

# ─── Phase 2: Determine scope ───────────────────────────────────────────────
echo -e "${YLW}── Phase 2: Determining audit scope ──${RST}"

mkdir -p .gemini

case "$MODE" in
    --full)
        FILES=$(find src/ tests/ scripts/ -name "*.py" -o -name "*.sh" | sort)
        FILES="$FILES config.yaml CLAUDE.md GEMINI.md"
        SCOPE="full codebase"
        ;;
    --security)
        FILES=$(find src/ scripts/ -name "*.py" -o -name "*.sh" | sort)
        SCOPE="security-focused"
        ;;
    --pre-push)
        FILES=$(find src/ tests/ scripts/ -name "*.py" -o -name "*.sh" | sort)
        FILES="$FILES config.yaml CLAUDE.md GEMINI.md"
        SCOPE="pre-push (full)"
        ;;
    --changes|*)
        if [[ -f "$MARKER_FILE" ]]; then
            LAST_COMMIT=$(cat "$MARKER_FILE")
            FILES=$(git diff --name-only "$LAST_COMMIT" HEAD -- 'src/*.py' 'tests/*.py' 'scripts/*.sh' 'config.yaml' 'CLAUDE.md' 'GEMINI.md' 2>/dev/null || echo "")
        else
            FILES=$(git diff --name-only HEAD~5 HEAD -- 'src/*.py' 'tests/*.py' 'scripts/*.sh' 'config.yaml' 'CLAUDE.md' 'GEMINI.md' 2>/dev/null || echo "")
        fi
        if [[ -z "$FILES" ]]; then
            echo "No code changes detected since last review. Use --full for complete audit."
            exit 0
        fi
        SCOPE="changes since last review"
        ;;
esac

FILE_COUNT=$(echo "$FILES" | wc -w)
echo "Scope: $SCOPE"
echo "Files: $FILE_COUNT"
echo ""

# ─── Phase 3: Build Gemini prompt ───────────────────────────────────────────
echo -e "${YLW}── Phase 3: Building audit prompt ──${RST}"

PROMPT="Read GEMINI.md in full — that is your review mandate.

Audit the following files ($SCOPE, $FILE_COUNT files):
$(echo "$FILES" | tr ' ' '\n' | sed 's/^/- /')

For each file, evaluate against the 7 Review Mandate dimensions:
1. Correctness & Logic
2. Architecture Conformance
3. Robustness & Error Handling
4. Security & Secrets
5. Code Quality & Maintainability
6. Testing
7. Documentation"

if [[ "$MODE" == "--security" ]]; then
    PROMPT="$PROMPT

SECURITY-FOCUSED AUDIT — give extra weight to these checks:
- API keys, tokens, or credentials in source or logs
- Secrets in f-strings, print statements, or error messages
- Unsafe YAML loading (yaml.load without SafeLoader)
- eval/exec usage
- subprocess with shell=True
- HTTP without TLS (plain http://)
- verify=False on any request
- Missing input validation on user-supplied data
- Path traversal risks
- Dependencies with known vulnerabilities
- PII in YAML files, logs, or output
- .env and output/ properly gitignored
- API responses logged at INFO instead of DEBUG"
fi

PROMPT="$PROMPT

Present results as:

## Gemini Audit — $(date -u '+%Y-%m-%d %H:%M')
Scope: $SCOPE ($FILE_COUNT files)

### Executive Summary
- 🔴 Blockers: N
- 🟡 Issues: N
- 🟢 Suggestions: N

### File-by-File Findings
For each file with findings:
#### [filepath] (🔴 N / 🟡 N / 🟢 N)
- [classification] [line] Description + fix suggestion

### Security Findings
Any security-specific issues found.

### ✅ What's Good
Architecture strengths and positive patterns.

### Fix Roadmap
Ordered list of fixes for Claude Code to execute.

Be thorough. Read every file listed. If a file is clean, say so explicitly."

# ─── Phase 4: Execute Gemini ────────────────────────────────────────────────
echo -e "${YLW}── Phase 4: Running Gemini audit ──${RST}"

if ! command -v gemini &>/dev/null; then
    echo -e "${RED}❌ Gemini CLI not found. Install with: npm install -g @google/gemini-cli${RST}"
    echo ""
    echo "Prompt saved to .gemini/pending_prompt.txt — run manually when available."
    echo "$PROMPT" > .gemini/pending_prompt.txt
    exit 1
fi

echo "This may take 2-5 minutes..."
echo ""

# Run Gemini and capture output
GEMINI_OUTPUT=$(gemini -p "$PROMPT" 2>&1) || true

# ─── Phase 5: Save report ──────────────────────────────────────────────────
echo -e "${YLW}── Phase 5: Saving report ──${RST}"

if [[ -f "$REPORT_FILE" ]]; then
    # Prepend new audit to existing report
    TEMP_FILE=$(mktemp)
    echo "$GEMINI_OUTPUT" > "$TEMP_FILE"
    echo "" >> "$TEMP_FILE"
    echo "---" >> "$TEMP_FILE"
    echo "" >> "$TEMP_FILE"
    cat "$REPORT_FILE" >> "$TEMP_FILE"
    mv "$TEMP_FILE" "$REPORT_FILE"
else
    echo "$GEMINI_OUTPUT" > "$REPORT_FILE"
fi

# Update marker
git rev-parse HEAD > "$MARKER_FILE"

echo "Report saved to: $REPORT_FILE"
echo "Review marker updated to: $(cat $MARKER_FILE)"
echo ""

# ─── Phase 6: Summary ──────────────────────────────────────────────────────
BLOCKERS=$(grep -c "🔴" "$REPORT_FILE" 2>/dev/null || echo "0")
ISSUES=$(grep -c "🟡" "$REPORT_FILE" 2>/dev/null || echo "0")

echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo -e "${BLU} AUDIT COMPLETE${RST}"
echo -e "${BLU}═══════════════════════════════════════════════════════════${RST}"
echo ""
echo "  Report: $REPORT_FILE"
echo "  🔴 Blockers found: ~$BLOCKERS"
echo "  🟡 Issues found: ~$ISSUES"
echo ""

if [[ "$MODE" == "--pre-push" ]] && [[ "$BLOCKERS" -gt 2 ]]; then
    echo -e "${RED}⚠️  Multiple blockers detected. Review audit_report.md before pushing.${RST}"
    exit 1
fi

echo -e "${GRN}✅ Audit complete. Review audit_report.md for details.${RST}"
echo ""
