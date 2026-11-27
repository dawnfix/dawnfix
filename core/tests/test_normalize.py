import json

import pytest

from dawnfix_core.normalize import (
    Event, error_stem, fingerprint, parse_log_message, route_template, service_name,
)


@pytest.mark.parametrize("url, want", [
    ("/users/123/orders/456", "/users/:id/orders/:id"),
    ("/users/3f2b8c1e-9a4d-4e2f-8b1a-2c3d4e5f6a7b", "/users/:id"),
    ("/users/507f1f77bcf86cd799439011/x", "/users/:id/x"),
    ("/mail/jane%40example.com/inbox", "/mail/:email/inbox"),
    ("/mail/jane%2540example.com", "/mail/:email"),
    ("/files/abcdefghijklmnopqrstuvwxyz", "/files/:id"),
    ("/search?q=jane@example.com", "/search"),
    ("https://api.example.com/v1/items/42?x=1", "/v1/items/:id"),
    ("/files/my report.pdf", "/files/:x"),
    ("/health", "/health"),
    ("", ""),
])
def test_route_template(url, want):
    assert route_template(url) == want


def test_route_template_caps_depth():
    r = route_template("/a" * 40)
    assert r.endswith("/...") and len(r) <= 200


def test_pino_json():
    line = json.dumps({"level": 50, "req": {"method": "post", "url": "/orders/99?coupon=X"},
                       "res": {"statusCode": 500}, "err": {"type": "TypeError", "message": "x is undefined"}})
    p = parse_log_message(line)
    assert p == {"method": "POST", "route": "/orders/:id", "status": 500, "error_class": "TypeError",
                 "message": "x is undefined", "is_error": True}


def test_audit_json_info_is_not_error():
    p = parse_log_message(json.dumps({"type": "audit", "path": "/users/1", "status": 200}))
    assert p["is_error"] is False


def test_text_access_line():
    p = parse_log_message("GET /users/12345/avatar 502 31ms")
    assert (p["method"], p["route"], p["status"], p["error_class"], p["is_error"]) == \
        ("GET", "/users/:id/avatar", 502, "HTTP502", True)
    assert p["message"] == ""


def test_text_error_with_errno():
    p = parse_log_message("27.10.2026 10:00:01.123 [ERROR] socket hang up ECONNRESET")
    assert p["is_error"] and p["error_class"] == "ECONNRESET"


def test_stem_folds_variable_parts():
    a = error_stem("2026-10-27T10:00:00Z [ERROR] Timeout after 3012ms for jane@example.com")
    b = error_stem("2026-10-27T11:30:12Z [ERROR] Timeout after 15ms for bob@example.com")
    assert a == b == "Timeout after :nms for :email"


def test_stem_empty_message_uses_status():
    assert error_stem("", 503) == "HTTP 503"


def test_fingerprint_stable_and_distinct():
    fp = fingerprint("aws", "my-api-prod", "/users/:id", "x is undefined")
    assert fp == fingerprint("aws", "my-api-prod", "/users/:id", "x is undefined")
    assert len(fp) == 16 and int(fp, 16) >= 0
    assert fp != fingerprint("gcp", "my-api-prod", "/users/:id", "x is undefined")
    assert fp != fingerprint("aws", "my-api-prod", "/orders/:id", "x is undefined")
    # Pinned: changing the hash input breaks every customer's state file.
    assert fp == "cb07296de0cdae40"


def test_same_error_different_ids_same_fingerprint():
    def ev(url, msg):
        p = parse_log_message(f"GET {url} 500 TypeError: {msg}")
        return Event(source="aws", source_id="aws:us-east-1", kind="log", service="my-api-prod",
                     route=p["route"], status=p["status"], message=p["message"], error_class=p["error_class"])

    assert ev("/users/1", "user 1 failed").fingerprint == ev("/users/987654", "user 987654 failed").fingerprint
    assert ev("/users/1", "a").fingerprint != ev("/users/1", "b").fingerprint


def test_service_name_is_safe():
    assert service_name("/ecs/my-api-prod") == "ecs/my-api-prod"
    assert service_name("weird name\n") == "weird_name"
