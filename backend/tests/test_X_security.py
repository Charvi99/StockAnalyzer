"""
X security/config audit — source-inspection tests (runnable, no DB/deps):
    python3 backend/tests/test_X_security.py

Locks in the X1 positives and the known issues:
  POSITIVE — .env is gitignored; only .env.example tracked (no secret leak).
  POSITIVE — API keys come from os.getenv, not hardcoded.
  X1.1     — CORS currently allows wildcard origins + credentials (the gating risk).
  X1.2     — database.py default DATABASE_URL embeds a weak password (stockpass123).
"""
import os
import sys
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND = os.path.join(REPO, "backend")


def _git(cmd):
    return subprocess.run(["git", "-C", REPO] + cmd, capture_output=True, text=True).stdout


def _read(rel):
    with open(os.path.join(BACKEND, rel)) as fh:
        return fh.read()


def test_positive_env_gitignored_only_example_tracked():
    tracked = _git(["ls-files"]).splitlines()
    env_tracked = [f for f in tracked if os.path.basename(f) == ".env" or f.endswith(".env")]
    # .env.example is fine; a real .env committed would be a leak.
    leaks = [f for f in env_tracked if not f.endswith(".env.example")]
    assert not leaks, f"tracked .env files (secret leak): {leaks}"
    gi = _read("../.gitignore") if os.path.exists(os.path.join(REPO, ".gitignore")) else ""
    assert ".env" in gi, ".gitignore must cover .env"


def test_positive_api_keys_via_env_not_hardcoded():
    src = _read("app/services/polygon_fetcher.py") + "\n" + _read("app/services/quiverquant_fetcher.py")
    assert "os.getenv" in src and "POLYGON_API_KEY" in src and "QUIVERQUANT_API_KEY" in src, (
        "API keys must be read from env, not hardcoded"
    )
    # no obvious hardcoded long key literals assigned directly
    import re
    suspicious = re.findall(r"""api[_-]?key\s*=\s*['"][A-Za-z0-9_]{20,}['"]""", src, re.I)
    assert not suspicious, f"possible hardcoded API key: {suspicious}"


def test_x1_1_cors_allows_wildcard_with_credentials():
    """Locks the gating risk. If CORS is hardened, update this test + the X1.1 finding."""
    main = _read("app/main.py")
    assert 'allow_origins=["*"]' in main or "allow_origins=['*']" in main, (
        "CORS no longer wildcard — update docs/audit/X_security_hygiene.md X1.1"
    )
    assert "allow_credentials=True" in main, "credentials still enabled with wildcard origin"


def test_x1_2_db_default_has_weak_password():
    """Locks the config footgun. If the default is removed, update the X1.2 finding."""
    db = _read("app/db/database.py")
    assert "stockpass123" in db, (
        "DB default password changed/removed — update docs/audit/X_security_hygiene.md X1.2"
    )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}: {e}")
    print(f"\n{'All passed' if not failures else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
