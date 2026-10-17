from __future__ import annotations

from typing import Any

from selene_observability.scrubbing import scrub_data


def test_scrubber_redacts_all_required_keys_case_insensitively() -> None:
    data = {
        "AUTHORIZATION": "Bearer eyJhbGciOi...",
        "Cookie": "session_id=abc12345",
        "set-cookie": "token=xyz789",
        "Api_Key": "secret-api-key-value",
        "REFRESH_TOKEN": "refresh-token-value",
        "private_key": "-----BEGIN PRIVATE KEY-----...",
        "Password": "my-super-secret-password",
        "Secret": "vault-secret",
        "Token": "temporary-auth-token",
        "normal_field": "visible_value",
    }

    result = scrub_data(data)

    assert result["AUTHORIZATION"] == "[REDACTED]"
    assert result["Cookie"] == "[REDACTED]"
    assert result["set-cookie"] == "[REDACTED]"
    assert result["Api_Key"] == "[REDACTED]"
    assert result["REFRESH_TOKEN"] == "[REDACTED]"
    assert result["private_key"] == "[REDACTED]"
    assert result["Password"] == "[REDACTED]"
    assert result["Secret"] == "[REDACTED]"
    assert result["Token"] == "[REDACTED]"
    assert result["normal_field"] == "visible_value"


def test_scrubber_handles_arbitrary_nesting_and_collections() -> None:
    nested: dict[str, Any] = {
        "users": [
            {"id": "u-1", "password": "pass1", "profile": {"email": "u1@selene.local"}},
            {"id": "u-2", "TOKEN": "tok2", "metadata": [{"API_KEY": "key2"}]},
        ],
        "system": {
            "auth": {
                "secret": "system-secret",
                "hosts": ("host1", "host2"),
            }
        },
    }

    result = scrub_data(nested)

    assert result["users"][0]["password"] == "[REDACTED]"
    assert result["users"][0]["profile"]["email"] == "u1@selene.local"
    assert result["users"][1]["TOKEN"] == "[REDACTED]"
    assert result["users"][1]["metadata"][0]["API_KEY"] == "[REDACTED]"
    assert result["system"]["auth"]["secret"] == "[REDACTED]"
    assert result["system"]["auth"]["hosts"] == ("host1", "host2")

    # Ensure original data was not mutated
    assert nested["users"][0]["password"] == "pass1"


def test_scrubber_handles_sets() -> None:
    data = {"secrets": {"password", "plain_text"}}
    result = scrub_data(data)
    assert isinstance(result["secrets"], set)
