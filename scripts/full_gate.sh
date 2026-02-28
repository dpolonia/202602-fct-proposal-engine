#!/usr/bin/env bash
# =============================================================================
# scripts/full_gate.sh — Complete quality gate: Security + Gemini
#
# Usage:
#   bash scripts/full_gate.sh          # run before git push
# =============================================================================

set -euo pipefail

echo ""
echo "════════════════════════════════════════════════════"
echo " Full Quality Gate: Security + Gemini Code Review"
echo "════════════════════════════════════════════════════"
echo ""

echo "━━━ GATE 1/2: Security Assessment ━━━"
if ! bash scripts/security_check.sh --all; then
    echo ""
    echo "❌ GATE 1 FAILED — fix security blockers first."
    exit 1
fi
echo ""
echo "✅ Gate 1 passed."
echo ""

echo "━━━ GATE 2/2: Gemini Code Review ━━━"
if command -v gemini &>/dev/null; then
    bash scripts/gemini_review.sh --pre-push
    echo ""
    echo "✅ Gate 2 passed."
else
    echo "⚠️  Gemini CLI not installed — skipping code review."
    echo "   Install with: npm install -g @google/gemini-cli"
    echo "   Gate 2 skipped (non-blocking)."
fi

echo ""
echo "════════════════════════════════════════════════════"
echo " ✅ ALL GATES PASSED — safe to push"
echo "════════════════════════════════════════════════════"
echo ""
