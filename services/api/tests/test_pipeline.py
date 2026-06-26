"""End-to-end pipeline orchestration via injected fakes.

We never call ffmpeg, yt-dlp, or any HTTP endpoint here. PipelineDeps
lets the test wire purely-Python stand-ins for each step.
"""

from pathlib import Path

import pytest

from app.repo import job_state
from app.service import pipeline as pipeline_module
from app.service.pipeline import PipelineDeps, YtDlpError, new_job, run_job
from app.types import Insight


@pytest.fixture(autouse=True)
def stub_jobs_index(monkeypatch):
    """Capture append_to_index calls so tests can assert pipeline behavior.

    Spies on `pipeline._record_in_index` indirectly by replacing the
    underlying `jobs_index.append_to_index` symbol. Pipelines must call
    the indexer once per landed job and skip it on hard failures.
    """
    calls: list = []

    def fake_append(entry):
        calls.append(entry)

    monkeypatch.setattr(pipeline_module.jobs_index, "append_to_index", fake_append)
    return calls


def _fake_download_factory(size_bytes: int = 1024):
    """Return a downloader that writes a tiny stub mp4 to disk."""

    def fake_download(url: str, out_path: str) -> dict:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00" * size_bytes)
        return {"path": out_path}

    return fake_download


def _make_deps(
    fake_b2,
    *,
    transcribe_result=None,
    insights_result=None,
    transcribe_raises: Exception | None = None,
    insights_raises: Exception | None = None,
    download_raises: Exception | None = None,
) -> PipelineDeps:
    def transcribe(chunks):
        if transcribe_raises:
            raise transcribe_raises
        return transcribe_result or {
            "text": "hello world",
            "segments": [{"id": 0, "start": 0, "end": 1, "text": "hello world"}],
            "model": "test-asr",
        }

    def extract_insights(transcript):
        if insights_raises:
            raise insights_raises
        return insights_result or [
            Insight(
                index=0,
                title="Intro",
                summary="A short intro.",
                start_seconds=0.0,
                end_seconds=5.0,
                key_quotes=[],
            )
        ]

    def download(url, out_path):
        if download_raises:
            raise download_raises
        return _fake_download_factory()(url, out_path)

    return PipelineDeps(
        download_video=download,
        probe_duration=lambda path: 30.0,
        extract_audio=lambda src, dst: Path(dst).write_bytes(b"WAV"),
        chunk_audio=lambda src, out_dir, n: [(src, 0.0)],
        transcribe=transcribe,
        extract_insights=extract_insights,
        put_file_to_b2=fake_b2.put_file,
        put_json_to_b2=fake_b2.put_json,
    )


async def test_happy_path_writes_all_four_objects(fake_b2, monkeypatch, stub_jobs_index):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-key")

    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    await run_job(status.job_id, deps=_make_deps(fake_b2))

    final = job_state.read(status.job_id)
    assert final is not None
    assert final.status == "done"
    assert final.analysis_status == "ok"
    assert final.result.source_key
    assert final.result.transcript_key
    assert final.result.insights_key
    assert final.result.manifest_key
    keys = set(fake_b2.objects)
    assert final.result.source_key in keys
    assert final.result.transcript_key in keys
    assert final.result.insights_key in keys
    assert final.result.manifest_key in keys

    # Successful job: indexer was called exactly once with the right
    # summary so the dashboard's previous-videos table renders it.
    assert len(stub_jobs_index) == 1
    entry = stub_jobs_index[0]
    assert entry.job_id == final.job_id
    assert entry.video_id == final.video_id
    assert entry.source_url == final.source_url
    assert entry.analysis_status == "ok"
    assert entry.insights_count == 1
    assert entry.manifest_key == final.result.manifest_key
    assert entry.source_key == final.result.source_key


async def test_no_api_key_falls_back_to_done_no_analysis(fake_b2, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "")  # the key signal

    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    await run_job(status.job_id, deps=_make_deps(fake_b2))

    final = job_state.read(status.job_id)
    assert final is not None
    assert final.status == "done_no_analysis"
    assert final.analysis_status == "skipped_no_api_key"
    # Source MUST land in B2 even when AI is skipped.
    assert final.result.source_key in fake_b2.objects
    # Manifest must still be written so the frontend can render the player.
    assert final.result.manifest_key in fake_b2.objects
    assert final.result.transcript_key is None
    assert final.result.insights_key is None


async def test_asr_failure_keeps_source_only(fake_b2, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-key")

    deps = _make_deps(fake_b2, transcribe_raises=RuntimeError("nim down"))
    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    await run_job(status.job_id, deps=deps)

    final = job_state.read(status.job_id)
    assert final is not None
    assert final.status == "done_no_analysis"
    assert final.analysis_status == "failed_asr"
    assert final.result.source_key in fake_b2.objects
    assert final.result.manifest_key in fake_b2.objects
    assert final.result.transcript_key is None
    assert final.result.insights_key is None


async def test_insights_failure_keeps_transcript(fake_b2, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-key")

    deps = _make_deps(fake_b2, insights_raises=RuntimeError("llm down"))
    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    await run_job(status.job_id, deps=deps)

    final = job_state.read(status.job_id)
    assert final is not None
    assert final.status == "done_no_analysis"
    assert final.analysis_status == "failed_insights"
    assert final.result.source_key in fake_b2.objects
    assert final.result.transcript_key in fake_b2.objects
    assert final.result.manifest_key in fake_b2.objects
    assert final.result.insights_key is None


async def test_cancel_during_transcribing_short_circuits(fake_b2, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-key")

    def transcribe_then_check(_chunks):
        # Caller sees cancel only after this stage starts; emulate that
        # by setting the flag right before this returns. The pipeline
        # checks _cancelled before the *next* stage and aborts.
        job_state.request_cancel(status.job_id)
        return {"text": "x", "segments": [{"start": 0, "end": 1, "text": "x"}], "model": "t"}

    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    deps = _make_deps(fake_b2)
    deps.transcribe = transcribe_then_check
    await run_job(status.job_id, deps=deps)

    final = job_state.read(status.job_id)
    assert final is not None
    assert final.status == "cancelled"
    # Source already landed before cancel was observed.
    assert final.result.source_key in fake_b2.objects
    # Manifest must NOT be written for cancelled jobs.
    assert final.result.manifest_key is None


async def test_yt_dlp_error_classified_and_fails_fast(fake_b2, stub_jobs_index):
    deps = _make_deps(
        fake_b2,
        download_raises=YtDlpError("yt_dlp_private_video", "Private video"),
    )
    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    await run_job(status.job_id, deps=deps)

    final = job_state.read(status.job_id)
    assert final is not None
    assert final.status == "failed"
    assert final.error is not None
    assert final.error.code == "yt_dlp_private_video"

    # Hard failure before B2 upload: nothing landed, so the indexer must
    # NOT be called — a stale row would point at a missing source video.
    assert stub_jobs_index == []


async def test_download_executable_missing_fails_fast(fake_b2, stub_jobs_index):
    deps = _make_deps(fake_b2, download_raises=FileNotFoundError("python missing"))
    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    await run_job(status.job_id, deps=deps)

    final = job_state.read(status.job_id)
    assert final is not None
    assert final.status == "failed"
    assert final.error is not None
    assert final.error.code == "yt_dlp_failed"
    assert "download executable unavailable" in final.error.message
    assert stub_jobs_index == []


async def test_workdir_cleaned_in_finally(fake_b2, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-key")

    status = new_job(video_id=None, source_url="https://www.youtube.com/watch?v=ok")
    work_subdir = Path(settings.work_dir) / status.video_id
    await run_job(status.job_id, deps=_make_deps(fake_b2))
    # finally: shutil.rmtree must have removed the per-video scratch dir.
    assert not work_subdir.exists()
