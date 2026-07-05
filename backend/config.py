"""Configuration from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    search_max_results: int = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
    search_provider: str = os.getenv("SEARCH_PROVIDER", "tavily")
    fetch_provider: str = os.getenv("FETCH_PROVIDER", "chain")
    fetch_max_chars: int = int(os.getenv("FETCH_MAX_CHARS", "8000"))
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    tavily_search_depth: str = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
    jina_api_key: str = os.getenv("JINA_API_KEY", "")
    extract_concurrency: int = int(os.getenv("EXTRACT_CONCURRENCY", "3"))
    planner_max_sections: int = int(os.getenv("PLANNER_MAX_SECTIONS", "5"))
    planner_initial_sources: int = int(os.getenv("PLANNER_INITIAL_SOURCES", "5"))
    deep_sources_per_query: int = int(os.getenv("DEEP_SOURCES_PER_QUERY", "3"))
    report_output_dir: str = os.getenv(
        "REPORT_OUTPUT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "reports"),
    )


config = Config()
