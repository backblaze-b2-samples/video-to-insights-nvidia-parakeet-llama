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
