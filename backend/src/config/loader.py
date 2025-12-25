import os
from typing import Any, Dict

import yaml


def get_bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def get_str_env(name: str, default: str = "") -> str:
    val = os.getenv(name)
    return default if val is None else str(val).strip()


def get_int_env(name: str, default: int = 0) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        print(f"Invalid integer value for {name}: {val}. Using default {default}.")
        return default


def replace_env_vars(value: str) -> str:
    """Replace environment variables in string values."""
    if not isinstance(value, str):
        return value
    if value.startswith("$"):
        env_var = value[1:]
        return os.getenv(env_var, env_var)
    return value


def process_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively process dictionary to replace environment variables."""
    if not config:
        return {}
    result = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = process_dict(value)
        elif isinstance(value, str):
            result[key] = replace_env_vars(value)
        else:
            result[key] = value
    return result


_config_cache: Dict[str, Dict[str, Any]] = {}


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """Load and process YAML configuration file."""
    # Adapter: If loading "conf.yaml", return configuration from centralized Settings
    # This bridges legacy code dependent on conf.yaml to the new Env/Settings system.
    if file_path.endswith("conf.yaml"):
        from backend.core.conf import settings
        
        return {
            # LLM Provider Configuration (new provider-based system)
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "LLM_MAX_RETRIES": settings.LLM_MAX_RETRIES,
            "LLM_TOKEN_LIMIT": settings.LLM_TOKEN_LIMIT,
            "LLM_TEMPERATURE": settings.LLM_TEMPERATURE,
            
            # Search Engine Configuration
            "SEARCH_ENGINE": {
                "engine": settings.AGENT_SEARCH_ENGINE,
                "include_domains": settings.SEARCH_ENGINE_INCLUDE_DOMAINS,
                "exclude_domains": settings.SEARCH_ENGINE_EXCLUDE_DOMAINS,
                "include_answer": settings.SEARCH_ENGINE_INCLUDE_ANSWER,
                "search_depth": settings.SEARCH_ENGINE_SEARCH_DEPTH,
                "include_raw_content": settings.SEARCH_ENGINE_INCLUDE_RAW_CONTENT,
                "include_images": settings.SEARCH_ENGINE_INCLUDE_IMAGES,
                "include_image_descriptions": settings.SEARCH_ENGINE_INCLUDE_IMAGE_DESCRIPTIONS,
                "min_score_threshold": settings.SEARCH_ENGINE_MIN_SCORE_THRESHOLD,
                "max_content_length_per_page": settings.SEARCH_ENGINE_MAX_CONTENT_LENGTH,
                # InfoQuest specific
                "time_range": settings.SEARCH_ENGINE_TIME_RANGE,
                "site": settings.SEARCH_ENGINE_SITE,
            },
            "CRAWLER_ENGINE": {
                "engine": settings.CRAWLER_ENGINE,
                "fetch_time": settings.CRAWLER_FETCH_TIME,
                "timeout": settings.CRAWLER_TIMEOUT,
                "navi_timeout": settings.CRAWLER_NAVI_TIMEOUT,
            },
            "ENABLE_PYTHON_REPL": settings.ENABLE_PYTHON_REPL,
            "TOOL_INTERRUPTS": {
                "interrupt_before": settings.TOOL_INTERRUPTS_BEFORE
            },
            # Map legacy simplified keys if needed by loose tool implementations
            "TAVILY_API_KEY": settings.TAVILY_API_KEY,
            "INFOQUEST_API_KEY": settings.INFOQUEST_API_KEY,
            "JINA_API_KEY": settings.JINA_API_KEY,
            "SEARX_HOST": settings.SEARX_HOST,
        }

    # 如果文件不存在，返回{}
    if not os.path.exists(file_path):
        return {}

    # 检查缓存中是否已存在配置
    if file_path in _config_cache:
        return _config_cache[file_path]

    # 如果缓存中不存在，则加载并处理配置
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
    processed_config = process_dict(config)

    # 将处理后的配置存入缓存
    _config_cache[file_path] = processed_config
    return processed_config
