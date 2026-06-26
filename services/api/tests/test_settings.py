import pytest

from app.config.settings import Settings


def test_b2_s3_url_is_derived_from_region():
    settings = Settings(
        b2_application_key_id="key-id",
        b2_application_key="app-key",
        b2_bucket_name="bucket",
        b2_region="us-test-001",
        _env_file=None,
    )

    assert settings.b2_s3_endpoint_url == "https://s3.us-test-001.backblazeb2.com"


def test_b2_public_url_base_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("B2_PUBLIC_URL_BASE", raising=False)
    settings = Settings(_env_file=None)

    assert settings.b2_public_url_base == ""


@pytest.mark.parametrize(
    "region",
    [
        "attacker.example:443/x",
        "evil.com:443#frag",
        "evil%2fhost",
        "evil@host",
        " ",
        "us-test-001/path",
    ],
)
def test_b2_region_rejects_unsafe_values(region):
    with pytest.raises(ValueError, match="B2_REGION"):
        Settings(b2_region=region, _env_file=None)


def test_standard_key_id_precedes_legacy_rollout_fallback(monkeypatch):
    monkeypatch.setenv("B2_APPLICATION_KEY_ID", "standard-id")
    monkeypatch.setenv("B2_KEY_ID", "legacy-id")

    settings = Settings(_env_file=None)

    assert settings.b2_application_key_id == "standard-id"


def test_legacy_key_id_supported_for_rollout(monkeypatch):
    monkeypatch.delenv("B2_APPLICATION_KEY_ID", raising=False)
    monkeypatch.setenv("B2_KEY_ID", "legacy-id")

    settings = Settings(_env_file=None)

    assert settings.b2_application_key_id == "legacy-id"
