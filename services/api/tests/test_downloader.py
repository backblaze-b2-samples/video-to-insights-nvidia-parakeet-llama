import subprocess

import pytest

from app.service import downloader


def test_default_download_missing_module_includes_api_env_hint(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            1,
            stderr="/usr/bin/python: No module named 'yt_dlp'\n",
        )

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)

    with pytest.raises(downloader.YtDlpError) as exc:
        downloader.default_download(
            "https://www.youtube.com/watch?v=ok",
            str(tmp_path / "source.mp4"),
        )

    assert exc.value.code == "yt_dlp_failed"
    assert "API Python environment" in exc.value.message
    assert "pip install -r requirements.txt" in exc.value.message
