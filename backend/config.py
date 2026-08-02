"""Configuration from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    # Brief / research-plan writing: prefer strongest model (defaults to LLM_MODEL)
    llm_brief_model: str = os.getenv("LLM_BRIEF_MODEL", "").strip()

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
    verifier_similarity_threshold: float = float(os.getenv("VERIFIER_SIMILARITY_THRESHOLD", "0.75"))
    verifier_max_revisions: int = int(os.getenv("VERIFIER_MAX_REVISIONS", "1"))
    multihop_max_hops: int = int(os.getenv("MULTIHOP_MAX_HOPS", "2"))
    multihop_sources_per_query: int = int(os.getenv("MULTIHOP_SOURCES_PER_QUERY", "3"))
    research_recency_days: int = int(os.getenv("RESEARCH_RECENCY_DAYS", "90"))
    dach_seeds_enabled: bool = os.getenv("DACH_SEEDS_ENABLED", "true").lower() in ("1", "true", "yes")
    dach_max_seed_queries: int = int(os.getenv("DACH_MAX_SEED_QUERIES", "5"))
    dach_seed_results_per_query: int = int(os.getenv("DACH_SEED_RESULTS_PER_QUERY", "3"))
    router_enabled: bool = os.getenv("ROUTER_ENABLED", "true").lower() in ("1", "true", "yes")
    router_max_sources_per_round: int = int(os.getenv("ROUTER_MAX_SOURCES_PER_ROUND", "6"))
    router_max_site_queries: int = int(os.getenv("ROUTER_MAX_SITE_QUERIES", "5"))
    router_max_direct_fetches: int = int(os.getenv("ROUTER_MAX_DIRECT_FETCHES", "4"))
    research_max_hops: int = int(os.getenv("RESEARCH_MAX_HOPS", "5"))
    research_max_router_calls: int = int(os.getenv("RESEARCH_MAX_ROUTER_CALLS", "4"))
    research_coverage_threshold: float = float(os.getenv("RESEARCH_COVERAGE_THRESHOLD", "0.65"))
    query_expand_max_per_hop: int = int(os.getenv("QUERY_EXPAND_MAX_PER_HOP", "8"))
    open_max_queries_per_hop: int = int(os.getenv("OPEN_MAX_QUERIES_PER_HOP", "6"))
    open_search_parallel: bool = os.getenv("OPEN_SEARCH_PARALLEL", "true").lower() in (
        "1", "true", "yes",
    )
    fetch_top_k_per_hop: int = int(os.getenv("FETCH_TOP_K_PER_HOP", "12"))
    tavily_deep_on_gap_hop: bool = os.getenv("TAVILY_DEEP_ON_GAP", "true").lower() in ("1", "true", "yes")
    tavily_deep_on_open_web: bool = os.getenv("TAVILY_DEEP_ON_OPEN_WEB", "true").lower() in (
        "1", "true", "yes",
    )
    min_unique_domains_target: int = int(os.getenv("MIN_UNIQUE_DOMAINS_TARGET", "3"))
    watchlist_dir: str = os.getenv(
        "WATCHLIST_DIR",
        os.path.join(os.path.dirname(__file__), "..", "data", "watchlists"),
    )
    report_output_dir: str = os.getenv(
        "REPORT_OUTPUT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "reports"),
    )
    cors_origins: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,https://yiwang.dev,https://search.yiwang.dev,https://search-demo.yiwang.dev,https://search-agent-seven.vercel.app",
    )
    site_password: str = os.getenv("SITE_PASSWORD", "")
    api_auth_secret: str = os.getenv("API_AUTH_SECRET", "")
    api_token_ttl_seconds: int = int(os.getenv("API_TOKEN_TTL_SECONDS", "86400"))


config = Config()
