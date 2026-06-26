from app.repo import b2_client


def test_s3_client_uses_standard_b2_contract(monkeypatch):
    calls = []
    fake_client = object()

    def record_client(service_name, **kwargs):
        calls.append((service_name, kwargs))
        return fake_client

    monkeypatch.setattr(b2_client.settings, "b2_application_key_id", "key-id")
    monkeypatch.setattr(b2_client.settings, "b2_application_key", "app-key")
    monkeypatch.setattr(b2_client.settings, "b2_bucket_name", "bucket")
    monkeypatch.setattr(b2_client.settings, "b2_region", "us-test-001")
    monkeypatch.setattr(b2_client.boto3, "client", record_client)

    b2_client.get_s3_client.cache_clear()
    try:
        assert b2_client.get_s3_client() is fake_client
    finally:
        b2_client.get_s3_client.cache_clear()

    service_name, kwargs = calls[0]
    assert service_name == "s3"
    assert kwargs["endpoint_url"] == "https://s3.us-test-001.backblazeb2.com"
    assert kwargs["region_name"] == "us-test-001"
    assert kwargs["aws_access_key_id"] == "key-id"
    assert kwargs["aws_secret_access_key"] == "app-key"
    assert kwargs["config"].user_agent_extra == b2_client.USER_AGENT_EXTRA
