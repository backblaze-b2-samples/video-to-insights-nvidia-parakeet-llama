from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Backblaze B2 (S3-compatible). Names per parent sampleapps/CLAUDE.md —
    # no AWS_*, no B2_S3_*. Region is derived from the bucket; we keep it
    # explicit so boto3's signing region is set correctly without inferring
    # from the endpoint URL.
    b2_endpoint: str = ""
    b2_region: str = ""
    b2_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    @property
    def allowed_hosts(self) -> list[str]:
        return [h.strip().lower() for h in self.allowed_video_hosts.split(",") if h.strip()]


settings = Settings()
