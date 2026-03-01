#!/usr/bin/env python3
"""
Scopus API Key Diagnostic Tool
===============================
Tests every common failure mode for Scopus API returning 0 results.

Usage:
  python3 test_scopus_key.py                     # reads from .env
  python3 test_scopus_key.py YOUR_API_KEY_HERE    # direct key
  SCOPUS_API_KEY=xxx python3 test_scopus_key.py   # env var

Common causes of 0 results:
  1. Key is an Institutional Token (insttoken) not an API Key
  2. Key lacks the "Scopus Search" product entitlement
  3. IP-based restrictions (key only works from institutional network)
  4. Query syntax errors (field codes, Boolean operators)
  5. Wrong base URL or endpoint
  6. Rate limiting (429) or quota exhaustion
  7. URL encoding issues with special characters
"""

import contextlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
BASE_URL = "https://api.elsevier.com/content/search/scopus"
AUTHOR_URL = "https://api.elsevier.com/content/search/author"
ABSTRACT_URL = "https://api.elsevier.com/content/abstract/scopus_id"
AUTH_CHECK_URL = "https://api.elsevier.com/authenticate"

# Known Scopus IDs for validation (Daniel Polónia)
KNOWN_AUTHOR_ID = "6506834325"
KNOWN_DOI = "10.1007/s10551-015-2760-8"  # Rego, Cunha, Polónia 2017 - 81 citations
KNOWN_TITLE_WORDS = "Corporate sustainability view from top"


# ─────────────────────────────────────────────
# Get the API key
# ─────────────────────────────────────────────
def get_api_key():
    """Try multiple sources for the Scopus API key."""
    # 1. Command line argument
    if len(sys.argv) > 1:
        return sys.argv[1].strip(), "command line argument"

    # 2. Environment variable
    key = os.environ.get("SCOPUS_API_KEY", "").strip()
    if key:
        return key, "SCOPUS_API_KEY environment variable"

    # 3. .env file (current directory)
    for env_path in [".env", "../.env"]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SCOPUS_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val, f"{env_path} file"

    return None, None


def make_request(url, api_key, use_insttoken=False):
    """Make a request to Scopus API with proper error handling."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "FCT-Proposal-Engine/1.0",
    }

    if use_insttoken:
        headers["X-ELS-Insttoken"] = api_key
    else:
        headers["X-ELS-APIKey"] = api_key

    req = urllib.request.Request(url, headers=headers)

    # Allow self-signed certs (some institutional proxies)
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            status = resp.status
            data = json.loads(resp.read().decode())
            rate_limit = resp.headers.get("X-RateLimit-Limit", "?")
            rate_remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            rate_reset = resp.headers.get("X-RateLimit-Reset", "?")
            return {
                "status": status,
                "data": data,
                "rate_limit": rate_limit,
                "rate_remaining": rate_remaining,
                "rate_reset": rate_reset,
                "error": None,
            }
    except urllib.error.HTTPError as e:
        body = ""
        with contextlib.suppress(Exception):
            body = e.read().decode()[:500]
        return {
            "status": e.code,
            "data": None,
            "error": f"HTTP {e.code}: {e.reason}",
            "body": body,
            "rate_limit": e.headers.get("X-RateLimit-Limit", "?") if e.headers else "?",
            "rate_remaining": e.headers.get("X-RateLimit-Remaining", "?") if e.headers else "?",
            "rate_reset": e.headers.get("X-RateLimit-Reset", "?") if e.headers else "?",
        }
    except Exception as e:
        return {"status": 0, "data": None, "error": str(e)}


def count_results(data):
    """Extract result count from Scopus response."""
    if not data:
        return -1
    sr = data.get("search-results", {})
    total = sr.get("opensearch:totalResults", "0")
    return int(total)


def print_header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_test(name, passed, detail=""):
    icon = "✓" if passed else "✗"
    print(f"  {icon} {name}")
    if detail:
        for line in detail.split("\n"):
            print(f"    {line}")


# ─────────────────────────────────────────────
# Main diagnostic sequence
# ─────────────────────────────────────────────
def main():
    print_header("SCOPUS API KEY DIAGNOSTIC TOOL")

    api_key, source = get_api_key()
    if not api_key:
        print("  ✗ No API key found!")
        print("    Provide it as:")
        print("    - Command line: python3 test_scopus_key.py YOUR_KEY")
        print("    - Env variable: SCOPUS_API_KEY=xxx python3 test_scopus_key.py")
        print("    - .env file:    SCOPUS_API_KEY=xxx in .env")
        sys.exit(1)

    print(f"  Key source: {source}")
    masked = f"{api_key[:4]}****{api_key[-2:]}"
    key_len = len(api_key)
    print(f"  Key value:  {masked} ({key_len} chars)")
    print()

    # ─── TEST 1: Key format ───
    print_header("TEST 1: Key Format Validation")

    issues = []
    if len(api_key) < 20:
        issues.append(
            f"Key too short ({len(api_key)} chars). Typical Scopus API key is 32 hex chars."
        )
    if len(api_key) > 64:
        issues.append(f"Key too long ({len(api_key)} chars). May be an insttoken or combined key.")
    if " " in api_key:
        issues.append("Key contains spaces — likely a copy-paste error.")
    if api_key.startswith('"') or api_key.startswith("'"):
        issues.append("Key starts with quote — remove surrounding quotes.")
    if not all(c in "0123456789abcdefABCDEF" for c in api_key):
        non_hex = [c for c in api_key if c not in "0123456789abcdefABCDEF"]
        issues.append(
            f"Key contains non-hex characters: {non_hex[:5]}."
            " Standard Scopus API keys are hex-only."
        )

    if issues:
        for issue in issues:
            print_test("Format check", False, issue)
    else:
        print_test("Format check", True, f"{len(api_key)} hex characters — looks correct")

    # ─── TEST 2: Authentication endpoint ───
    print_header("TEST 2: Authentication Check")

    result = make_request(AUTH_CHECK_URL, api_key)
    if result["status"] == 200:
        print_test("Auth endpoint", True, "Key is recognised by Elsevier")
    elif result["status"] == 401:
        print_test(
            "Auth endpoint",
            False,
            "401 Unauthorized — key is INVALID or EXPIRED.\n"
            "Go to https://dev.elsevier.com/apikey/manage to check.",
        )
    elif result["status"] == 403:
        print_test(
            "Auth endpoint",
            False,
            "403 Forbidden — key exists but may have IP restrictions.\n"
            "Check if your key is limited to institutional IP ranges.",
        )
    else:
        print_test(
            "Auth endpoint",
            False,
            f"Unexpected response: {result.get('error', result['status'])}\n"
            "This endpoint may not work for all key types — continuing.",
        )

    # ─── TEST 3: Simple search (broad query, should return thousands) ───
    print_header("TEST 3: Broad Search (should return >0 results)")

    queries = [
        ("TITLE(healthcare)", "Generic 'healthcare' title search"),
        ("TITLE(innovation)", "Generic 'innovation' title search"),
        ("ALL(synthetic data)", "Generic 'synthetic data' search"),
    ]

    any_worked = False
    for query, desc in queries:
        url = f"{BASE_URL}?query={urllib.parse.quote(query)}&count=1"
        result = make_request(url, api_key)

        if result["status"] == 200:
            n = count_results(result["data"])
            passed = n > 0
            any_worked = any_worked or passed
            print_test(
                f"{desc}",
                passed,
                f"Results: {n:,}\nRate limit: {result['rate_remaining']}/{result['rate_limit']}",
            )
        else:
            print_test(
                f"{desc}",
                False,
                f"HTTP {result['status']}: {result.get('error', '')}\n"
                f"{result.get('body', '')[:200]}",
            )

    if not any_worked:
        print()
        print("  ⚠ ALL broad queries returned 0 results.")
        print("  This usually means one of:")
        print("    (a) Your key is an Institutional Token, not an API Key")
        print("    (b) Your key doesn't have Scopus Search access")
        print("    (c) IP-based restriction (try from institutional network)")
        print()
        print("  Trying with X-ELS-Insttoken header instead...")

        # Retry as insttoken
        url = f"{BASE_URL}?query={urllib.parse.quote('TITLE(healthcare)')}&count=1"
        result = make_request(url, api_key, use_insttoken=True)
        if result["status"] == 200:
            n = count_results(result["data"])
            if n > 0:
                print_test(
                    "Insttoken mode",
                    True,
                    f"Results: {n:,}\n"
                    "⚠ Your key is an INSTITUTIONAL TOKEN, not an API Key!\n"
                    "Use X-ELS-Insttoken header instead of X-ELS-APIKey.\n"
                    "Or generate a proper API key at https://dev.elsevier.com/apikey/manage",
                )

    # ─── TEST 4: Author search (known author) ───
    print_header("TEST 4: Author-Specific Search")

    # By Author ID
    query = f"AU-ID({KNOWN_AUTHOR_ID})"
    url = f"{BASE_URL}?query={urllib.parse.quote(query)}&count=5"
    result = make_request(url, api_key)

    if result["status"] == 200:
        n = count_results(result["data"])
        print_test(
            f"AU-ID({KNOWN_AUTHOR_ID})", n > 0, f"Results: {n} (expected: ~28 Scopus documents)"
        )
        if n > 0:
            entries = result["data"].get("search-results", {}).get("entry", [])
            for i, entry in enumerate(entries[:3]):
                title = entry.get("dc:title", "N/A")[:70]
                year = entry.get("prism:coverDate", "N/A")[:4]
                print(f"      [{i + 1}] ({year}) {title}")
    else:
        print_test(f"AU-ID({KNOWN_AUTHOR_ID})", False, f"{result.get('error', '')}")

    # By author name
    query = "AUTHLASTNAME(Polonia) AND AUTHFIRST(Daniel)"
    url = f"{BASE_URL}?query={urllib.parse.quote(query)}&count=5"
    result = make_request(url, api_key)

    if result["status"] == 200:
        n = count_results(result["data"])
        print_test("Name search (Polonia, Daniel)", n > 0, f"Results: {n}")
    else:
        print_test("Name search", False, f"{result.get('error', '')}")

    # ─── TEST 5: DOI search (known publication) ───
    print_header("TEST 5: DOI Search (known publication)")

    query = f"DOI({KNOWN_DOI})"
    url = f"{BASE_URL}?query={urllib.parse.quote(query)}&count=1"
    result = make_request(url, api_key)

    if result["status"] == 200:
        n = count_results(result["data"])
        print_test(
            f"DOI: {KNOWN_DOI}",
            n > 0,
            f"Results: {n} (expected: 1 — Rego, Cunha & Polónia, 2017, J Business Ethics)",
        )
        if n > 0:
            entry = result["data"]["search-results"]["entry"][0]
            print(f"      Title: {entry.get('dc:title', 'N/A')[:70]}")
            print(f"      Cited: {entry.get('citedby-count', 'N/A')} times")
    else:
        print_test("DOI search", False, f"{result.get('error', '')}")

    # ─── TEST 6: Topic queries (the ones used in the engine) ───
    print_header("TEST 6: Engine-Style Topic Queries")

    engine_queries = [
        "synthetic health data governance",
        "value-based healthcare Beveridgean",
        "European Health Data Space regulation",
        "open innovation health data ecosystem",
        "synthetic patient data Synthea",
    ]

    for q in engine_queries:
        # Test as TITLE-ABS-KEY (standard Scopus field)
        query = f'TITLE-ABS-KEY("{q}")'
        url = f"{BASE_URL}?query={urllib.parse.quote(query)}&count=1"
        result = make_request(url, api_key)

        if result["status"] == 200:
            n = count_results(result["data"])
            status = "✓" if n > 0 else "⚠"
            print(f'  {status} TITLE-ABS-KEY("{q}"): {n:,} results')
        else:
            print(f'  ✗ TITLE-ABS-KEY("{q}"): {result.get("error", "")}')

    print()
    print("  Note: Some topic queries legitimately return 0 if the exact")
    print("  phrase doesn't exist in Scopus. Try without quotes:")
    print()

    # Retry without exact phrase matching
    for q in engine_queries[:2]:
        words = q.split()
        query = "TITLE-ABS-KEY(" + " AND ".join(words) + ")"
        url = f"{BASE_URL}?query={urllib.parse.quote(query)}&count=1"
        result = make_request(url, api_key)

        if result["status"] == 200:
            n = count_results(result["data"])
            status = "✓" if n > 0 else "⚠"
            print(f"  {status} AND-mode: {query[:60]}...: {n:,} results")

    # ─── TEST 7: Rate limits ───
    print_header("TEST 7: Rate Limit Status")

    url = f"{BASE_URL}?query=TITLE(test)&count=1"
    result = make_request(url, api_key)

    if result["status"] == 200 or result["status"] == 429:
        print(f"  Quota:     {result['rate_limit']} requests/week")
        print(f"  Remaining: {result['rate_remaining']}")
        print(f"  Reset:     {result['rate_reset']}")
        if result["rate_remaining"] != "?" and int(result["rate_remaining"]) == 0:
            print("  ⚠ QUOTA EXHAUSTED — this is why you're getting 0 results!")
            print("  Wait for reset or use a different key.")
    elif result["status"] == 429:
        print_test("Rate limit", False, "429 Too Many Requests — quota exhausted")

    # ─── SUMMARY ───
    print_header("SUMMARY & RECOMMENDATIONS")
    print()
    print("  If ALL tests return 0:")
    print("    1. Go to https://dev.elsevier.com/apikey/manage")
    print("    2. Check that your key has 'Scopus' in the Products list")
    print("    3. If it shows 'Institutional Token', you need the")
    print("       X-ELS-Insttoken header, not X-ELS-APIKey")
    print("    4. Try from your UA institutional network/VPN")
    print("    5. Create a NEW key: https://dev.elsevier.com/apikey/create")
    print("       Select 'Scopus Search API' as the product")
    print()
    print("  If broad queries work but topic queries return 0:")
    print("    → The queries use exact-phrase matching (quotes).")
    print("       Some niche phrases may genuinely have 0 Scopus results.")
    print("       Modify scopus_queries in the YAML to use broader terms.")
    print()
    print("  If author queries work but topic queries return 0:")
    print("    → Key is fine. The issue is query construction in the engine.")
    print("       Check how src/utils/ builds the Scopus query string.")
    print()


if __name__ == "__main__":
    main()
