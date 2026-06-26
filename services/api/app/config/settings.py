import re

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

B2_REGION_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class Settings(BaseSettings):
    # Backblaze B2 (S3-compatible). Keep the env surface on the standard
    # B2_* names and derive the S3 endpoint from the configured region.
    b2_application_key_id: str = Field(
        "",
        # Sunset: remove B2_KEY_ID fallback after 2026-07-31.
        # Tracked in docs/exec-plans/tech-debt-tracker.md.
        validation_alias=AliasChoices("B2_APPLICATION_KEY_ID", "B2_KEY_ID"),
    )
    b2_region: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    # Reserved by the B2 sample standard. This app currently serves
    # browser-facing artifacts through presigned URLs.
    b2_public_url_base: str = ""

    # NVIDIA NIM (free tier). When NVIDIA_API_KEY is empty the pipeline
    # short-circuits the analysis stages and the job finishes as
    # "done_no_analysis" with the source video still uploaded to B2.
    nvidia_api_key: str = ""
    nvidia_asr_model: str = "nvidia/parakeet-tdt-0.6b-v2"
    nvidia_insights_model: str = "meta/llama-3.3-70b-instruct"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # Pipeline knobs. WORK_DIR holds per-job temp directories and the
    # atomic-write job-state files (work_dir/jobs/{job_id}.json).
    work_dir: str = "./.work"
    max_video_seconds: int = 5400
    max_concurrent_jobs: int = 1
    allowed_video_hosts: str = (
        "youtube.com,youtu.be,m.youtube.com,www.youtube.com"
    )

    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    api_cors_origin_regex: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("b2_region")
    @classmethod
    def validate_b2_region(cls, value: str) -> str:
        if not value:
            return value
        region = value.strip()
        if region != value or not region or not B2_REGION_RE.fullmatch(region):
            raise ValueError(
                "B2_REGION must contain lowercase alphanumeric segments joined by hyphens"
            )
        return region

    @property
    def b2_s3_endpoint_url(self) -> str:
        if not self.b2_region:
            return ""
        return f"https://s3.{self.b2_region}.backblazeb2.com"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    @property
    def allowed_hosts(self) -> list[str]:
        return [h.strip().lower() for h in self.allowed_video_hosts.split(",") if h.strip()]


settings = Settings()
