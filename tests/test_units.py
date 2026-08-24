"""Pure functions: password hashing, relative time, rate limiter."""
import time

import main


def test_hash_pw_per_user_salt():
    """New format: fresh random per-user salt embedded as '<salt>$<hash>'."""
    h1 = main.hash_pw("hunter22")
    h2 = main.hash_pw("hunter22")
    assert h1 != h2                       # different salts each call
    assert h1.count("$") == 1
    salt, _, digest = h1.partition("$")
    assert len(salt) == 32 and len(digest) == 64  # 16B salt hex + sha256 hex
    assert main.verify_pw("hunter22", h1)
    assert not main.verify_pw("hunter23", h1)
    assert not main.verify_pw("hunter22", "not-a-hash")  # no '$', wrong legacy value


def test_verify_pw_legacy_global_salt():
    """Rows hashed with the old global-salt scheme still authenticate."""
    import hashlib
    legacy = hashlib.pbkdf2_hmac("sha256", b"oldpw", b"islatrade-salt", 120_000).hex()
    assert main.verify_pw("oldpw", legacy)
    assert not main.verify_pw("wrong", legacy)
    assert not main.verify_pw("x", None)


def test_ago_formatting():
    now = time.time()
    assert main.ago(now) == "0s ago"
    assert main.ago(now - 90) == "1m ago"
    assert main.ago(now - 2 * 3600) == "2h ago"
    assert main.ago(now - 3 * 86400) == "3d ago"
    assert main.ago("garbage") == ""


def test_rate_limit_blocks_after_limit_per_minute(monkeypatch):
    monkeypatch.setattr(main, "RL_LIMIT", 10)  # conftest raises it for flow tests
    ip = "203.0.113.99"
    assert all(main.rate_ok(ip) for _ in range(10))
    assert not main.rate_ok(ip)          # 11th inside window -> blocked
    main._RL[ip] = [time.time() - 120]   # window slid past -> allowed again
    assert main.rate_ok(ip)
