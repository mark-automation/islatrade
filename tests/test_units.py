"""Pure functions: password hashing, relative time, rate limiter."""
import time

import main


def test_hash_pw_deterministic_and_salted():
    assert main.hash_pw("hunter22") == main.hash_pw("hunter22")
    assert main.hash_pw("hunter22") != main.hash_pw("hunter23")
    assert len(main.hash_pw("x")) == 64  # sha256 hexdigest


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
