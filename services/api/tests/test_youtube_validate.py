"""URL allowlist + normalization for the submit endpoint."""

import pytest

from app.service.youtube import YouTubeValidationError, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc123",
        "https://youtube.com/watch?v=abc123",
        "https://m.youtube.com/watch?v=abc123",
        "https://youtu.be/abc123",
        "http://www.youtube.com/watch?v=abc123",
    ],
)
def test_valid_urls_pass(url):
    assert validate_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/123",
        "https://tiktok.com/@u/video/1",
        "https://example.com/youtube.com",  # endsWith vs subdomain mismatch
    ],
)
def test_unsupported_host_rejected(url):
    with pytest.raises(YouTubeValidationError) as ei:
        validate_url(url)
    assert ei.value.code == "unsupported_host"


def test_invalid_scheme_rejected():
    with pytest.raises(YouTubeValidationError) as ei:
        validate_url("ftp://youtube.com/x")
    assert ei.value.code == "invalid_url"


def test_empty_url_rejected():
    with pytest.raises(YouTubeValidationError) as ei:
        validate_url("")
    assert ei.value.code == "invalid_url"
