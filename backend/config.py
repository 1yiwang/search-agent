"""Configuration from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    search_max_results: int = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
    search_provider: str = os.getenv("SEARCH_PROVIDER", "ddg")
    fetch_provider: str = os.getenv("FETCH_PROVIDER", "httpx")
    fetch_max_chars: int = int(os.getenv("FETCH_MAX_CHARS", "8000"))
    report_output_dir: str = os.getenv(
        "REPORT_OUTPUT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "reports"),
    )


config = Config()
