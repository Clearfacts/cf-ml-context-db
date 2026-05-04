"""
Azure OpenAI LLM configuration for the context database project.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
import yaml
from cf_ml_common import llm as cf_llm
from cf_ml_common.llm import TokenTrackingConfig
from cf_ml_common.llm.persistence import get_create_table_sql
import logging

logger = logging.getLogger(__name__)

def init_token_tracking() -> None:
    """Initialise global token tracking with DB persistence.

    Uses the same DB_CONFIG_FILE / DB_SECTION environment variables that
    db_config.py uses, so no additional configuration is required in the Lambda.
    Tracking is skipped when CF_LLM_TRACKING_ENABLED is set to a falsy value.
    """
    enabled = os.environ.get("CF_LLM_TRACKING_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
    if not enabled:        
        return

    
    db_config_file = os.environ.get("DB_CONFIG_FILE", "config/database.ini")
    db_section = os.environ.get("DB_SECTION", "context_db")
    project = os.environ.get("CF_LLM_TRACKING_PROJECT", "cf-ml-context-db")

    cf_llm.reset_tracking()
    config = TokenTrackingConfig(
        project=project,
        enabled=True,
        persist_to_db=True,
        db_config_file=db_config_file,
        db_section=db_section,
    )
    cf_llm.init_token_tracking(config=config)
    logger.info(
        "[TokenTracking] Initialised — project=%s db_config=%s section=%s",
        project, db_config_file, db_section,
    )

    # Ensure the llm_token_usage table exists (idempotent — safe on every cold start)
    try:
        from mlbase.db import MlDatabaseDao
        dao = MlDatabaseDao(db_config_file, section=db_section)
        conn = dao.raw_connection()
        try:
            cur = conn.cursor()
            cur.execute(get_create_table_sql())
            conn.commit()
            cur.close()
            logger.info("[TokenTracking] llm_token_usage table ensured.")
        finally:
            conn.close()
    except Exception:
        logger.exception("[TokenTracking] Failed to ensure llm_token_usage table — tracking will still run but persistence may fail.")




def load_model_config(model_config_file):
    with open(model_config_file, "r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle)


def get_model_config(model_config_file, model_name):
    model_settings = load_model_config(model_config_file)
    for model_config in model_settings["azure_models"]:
        if model_config["name"] == model_name:
            return model_config
    raise ValueError(
        f"Model '{model_name}' not defined in azure_models in {model_config_file}."
    )


def _resolve_config_value(model_config: dict, key: str) -> str:
    env_key = f"{key}_env"
    if env_key in model_config:
        env_name = model_config[env_key]
        value = os.getenv(env_name)
        if not value:
            raise ValueError(
                f"Environment variable '{env_name}' is not set for model field '{key}'."
            )
        return value

    if key not in model_config:
        raise ValueError(f"Model config is missing required field '{key}'.")

    return model_config[key]


project_root = Path(__file__).resolve().parents[2]
load_dotenv(project_root / ".env")


def get_azure_llm(
    temperature: float = None,
    api_key: Optional[str] = None,
    model_name: str = "gpt-5-2025-08-07",
    max_tokens: int = 20000,
    use_responses_api: bool | None = None,
    reasoning: dict | None = None,
    api_version: str | None = None,
) -> AzureChatOpenAI:
    """Return a configured AzureChatOpenAI instance."""
    model_config_file = project_root / "config" / "fab_models.yaml"
    model_config = get_model_config(model_config_file, model_name)

    endpoint = _resolve_config_value(model_config, "end_point")
    deployment = model_config["name"]
    api_key = api_key or _resolve_config_value(model_config, "api_key")
    resolved_api_version = api_version or model_config["api_version"]

    if model_name.startswith("gpt-5-mini") or model_name.startswith("gpt-5-nano"):
        temperature = 1.0

    kwargs = dict(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        openai_api_version=resolved_api_version,
        openai_api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=240,
    )
    if use_responses_api is not None:
        kwargs["use_responses_api"] = use_responses_api
    if reasoning is not None:
        kwargs["reasoning"] = reasoning

    return AzureChatOpenAI(**kwargs)
