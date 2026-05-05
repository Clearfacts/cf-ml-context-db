from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


NAVIGATION_AGENT_MODEL_PROFILE_ENV = "NAVIGATION_AGENT_MODEL_PROFILE"
DEFAULT_NAVIGATION_AGENT_MODEL_CONFIG_PATH = (
    Path(__file__).resolve().parents[3] / "config" / "navigation_agent_models.yaml"
)


@dataclass(frozen=True)
class NavigationAgentRoleModelConfig:
    model_name: str
    max_tokens: int = 4000
    reasoning: dict[str, Any] | None = None


@dataclass(frozen=True)
class NavigationAgentModelProfile:
    name: str
    coordinator: NavigationAgentRoleModelConfig
    route_planner: NavigationAgentRoleModelConfig
    goal_assessor: NavigationAgentRoleModelConfig
    recovery: NavigationAgentRoleModelConfig
    validation: NavigationAgentRoleModelConfig
    ontology_batch_analyzer: NavigationAgentRoleModelConfig


REQUIRED_MODEL_ROLES = (
    "coordinator",
    "route_planner",
    "goal_assessor",
    "recovery",
    "validation",
    "ontology_batch_analyzer",
)


def available_navigation_agent_model_profiles(
    config_path: str | Path | None = None,
) -> list[str]:
    document = _load_profile_document(config_path)
    return sorted((document.get("profiles") or {}).keys())


def load_navigation_agent_model_profile(
    profile_name: str | None = None,
    *,
    config_path: str | Path | None = None,
) -> NavigationAgentModelProfile:
    document = _load_profile_document(config_path)
    profiles = document.get("profiles") or {}
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("Navigation agent model config must define at least one profile.")

    resolved_name = (
        profile_name
        or os.environ.get(NAVIGATION_AGENT_MODEL_PROFILE_ENV)
        or document.get("default_profile")
    )
    if not resolved_name:
        raise ValueError("Navigation agent model config must define default_profile or receive an explicit profile.")
    if resolved_name not in profiles:
        valid_profiles = ", ".join(sorted(profiles))
        raise ValueError(f"Unknown navigation agent model profile '{resolved_name}'. Valid profiles: {valid_profiles}.")

    profile = profiles[resolved_name]
    if not isinstance(profile, dict):
        raise ValueError(f"Navigation agent model profile '{resolved_name}' must be a mapping.")

    role_configs = {
        role_name: _parse_role_config(resolved_name, role_name, profile.get(role_name))
        for role_name in REQUIRED_MODEL_ROLES
    }
    return NavigationAgentModelProfile(name=resolved_name, **role_configs)


def single_model_navigation_agent_model_profile(
    *,
    model_name: str,
    max_tokens: int,
    ontology_reasoning: dict[str, Any] | None = None,
) -> NavigationAgentModelProfile:
    default_role = NavigationAgentRoleModelConfig(model_name=model_name, max_tokens=max_tokens)
    ontology_role = NavigationAgentRoleModelConfig(
        model_name=model_name,
        max_tokens=max_tokens,
        reasoning=ontology_reasoning,
    )
    return NavigationAgentModelProfile(
        name="single-model",
        coordinator=default_role,
        route_planner=default_role,
        goal_assessor=default_role,
        recovery=default_role,
        validation=default_role,
        ontology_batch_analyzer=ontology_role,
    )


def _load_profile_document(config_path: str | Path | None) -> dict[str, Any]:
    resolved_path = Path(config_path) if config_path is not None else DEFAULT_NAVIGATION_AGENT_MODEL_CONFIG_PATH
    if not resolved_path.exists():
        raise FileNotFoundError(f"Navigation agent model config not found: {resolved_path}")
    with resolved_path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    if not isinstance(document, dict):
        raise ValueError(f"Navigation agent model config must be a YAML mapping: {resolved_path}")
    return document


def _parse_role_config(
    profile_name: str,
    role_name: str,
    raw_config: Any,
) -> NavigationAgentRoleModelConfig:
    if not isinstance(raw_config, dict):
        raise ValueError(f"Profile '{profile_name}' must define a mapping for role '{role_name}'.")
    model_name = str(raw_config.get("model_name") or "").strip()
    if not model_name:
        raise ValueError(f"Profile '{profile_name}' role '{role_name}' must define model_name.")
    max_tokens = raw_config.get("max_tokens", 4000)
    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Profile '{profile_name}' role '{role_name}' has invalid max_tokens.") from exc
    if max_tokens <= 0:
        raise ValueError(f"Profile '{profile_name}' role '{role_name}' max_tokens must be positive.")

    reasoning = raw_config.get("reasoning")
    if reasoning is not None and not isinstance(reasoning, dict):
        raise ValueError(f"Profile '{profile_name}' role '{role_name}' reasoning must be a mapping.")
    return NavigationAgentRoleModelConfig(
        model_name=model_name,
        max_tokens=max_tokens,
        reasoning=reasoning,
    )
