"""Per-request LLM and search key overrides (BYOK, Step 32)."""
from contextvars import ContextVar
from dataclasses import dataclass

from openai import AsyncOpenAI

from config import config

_client_var: ContextVar["RequestKeys | None"] = ContextVar("request_keys", default=None)


@dataclass
class RequestKeys:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    tavily_api_key: str | None = None


def set_request_keys(keys: RequestKeys | None) -> None:
    _client_var.set(keys)


def get_request_keys() -> RequestKeys:
    override = _client_var.get()
    if override:
        return override
    return RequestKeys(
        llm_api_key=config.llm_api_key,
        llm_base_url=config.llm_base_url,
        llm_model=config.llm_model,
        tavily_api_key=config.tavily_api_key or None,
    )


def get_openai_client() -> AsyncOpenAI:
    keys = get_request_keys()
    return AsyncOpenAI(
        api_key=keys.llm_api_key,
        base_url=keys.llm_base_url,
    )


_WEAK_MODEL_MARKERS = (
    "mini", "flash", "haiku", "nano", "lite", "tiny", "small",
    "deepseek-chat", "deepseek-coder", "gpt-3.5", "qwen-turbo", "qwen-plus",
)


def get_strong_model() -> str:
    """Planning and writing use the strongest model, never a weak BYOK alias."""
    dedicated = (getattr(config, "llm_brief_model", None) or "").strip()
    if dedicated:
        return dedicated
    requested = (get_request_keys().llm_model or "").strip()
    server = (config.llm_model or "").strip() or "deepseek-v4-pro"
    if not requested or any(m in requested.lower() for m in _WEAK_MODEL_MARKERS):
        return server
    return requested


def get_tavily_api_key() -> str:
    keys = get_request_keys()
    return keys.tavily_api_key or config.tavily_api_key
