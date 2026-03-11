import os
from dataclasses import dataclass
from typing import Any, Literal

from openai import OpenAI

try:
    from azure.identity import (
        AzureCliCredential,
        ChainedTokenCredential,
        DefaultAzureCredential,
        get_bearer_token_provider,
    )
except ImportError:  # pragma: no cover - handled at runtime for API-key fallback compatibility
    AzureCliCredential = None
    ChainedTokenCredential = None
    DefaultAzureCredential = None
    get_bearer_token_provider = None


FOUNDRY_SCOPE = "https://ai.azure.com/.default"
AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass(frozen=True)
class FoundryAuthConfig:
    raw_endpoint: str
    base_url: str
    endpoint_family: Literal["foundry_project", "azure_openai"]
    scope: str
    auth_mode: Literal["azure_identity", "api_key"]


def build_credential() -> "ChainedTokenCredential":
    if AzureCliCredential is None or ChainedTokenCredential is None or DefaultAzureCredential is None:
        raise RuntimeError(
            "azure-identity is not installed. Run `uv sync --locked` after updating dependencies, "
            "or set FOUNDRY_AUTH_MODE=api_key to use the legacy path."
        )

    return ChainedTokenCredential(
        AzureCliCredential(),
        DefaultAzureCredential(exclude_cli_credential=True),
    )


def resolve_foundry_auth_config(endpoint_override: str | None = None) -> FoundryAuthConfig:
    raw_endpoint = _resolve_endpoint(endpoint_override=endpoint_override)
    endpoint_family = _detect_endpoint_family(raw_endpoint)
    scope = FOUNDRY_SCOPE if endpoint_family == "foundry_project" else AZURE_OPENAI_SCOPE
    base_url = _normalize_base_url(raw_endpoint, endpoint_family)
    auth_mode = _resolve_auth_mode()
    return FoundryAuthConfig(
        raw_endpoint=raw_endpoint,
        base_url=base_url,
        endpoint_family=endpoint_family,
        scope=scope,
        auth_mode=auth_mode,
    )


def build_openai_client_kwargs(
    *,
    endpoint_override: str | None = None,
    api_key_override: Any | None = None,
) -> tuple[dict[str, Any], FoundryAuthConfig]:
    config = resolve_foundry_auth_config(endpoint_override=endpoint_override)
    api_key = _resolve_openai_api_key(config, api_key_override=api_key_override)
    return {"base_url": config.base_url, "api_key": api_key}, config


def create_openai_client(
    *,
    endpoint_override: str | None = None,
    api_key_override: Any | None = None,
) -> tuple[OpenAI, FoundryAuthConfig]:
    client_kwargs, config = build_openai_client_kwargs(
        endpoint_override=endpoint_override,
        api_key_override=api_key_override,
    )
    return OpenAI(**client_kwargs), config


def describe_foundry_auth(config: FoundryAuthConfig) -> dict[str, str]:
    return {
        "raw_endpoint": config.raw_endpoint,
        "base_url": config.base_url,
        "endpoint_family": config.endpoint_family,
        "scope": config.scope,
        "auth_mode": config.auth_mode,
    }


def _resolve_auth_mode() -> Literal["azure_identity", "api_key"]:
    raw_mode = (os.getenv("FOUNDRY_AUTH_MODE") or "azure_identity").strip().lower()
    if raw_mode in {"azure_identity", "identity", "entra", "entra_id"}:
        return "azure_identity"
    if raw_mode in {"api_key", "key"}:
        return "api_key"
    raise RuntimeError(
        f"Unsupported FOUNDRY_AUTH_MODE={raw_mode!r}. Use 'azure_identity' or 'api_key'."
    )


def _resolve_endpoint(endpoint_override: str | None = None) -> str:
    endpoint = endpoint_override or (
        os.getenv("AZURE_AI_PROJECT_ENDPOINT")
        or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        or _build_project_endpoint_from_parts()
        or os.getenv("FOUNDRY_ENDPOINT")
        or os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    if not endpoint:
        raise RuntimeError(
            "Missing Foundry/Azure OpenAI endpoint. Set AZURE_AI_PROJECT_ENDPOINT, "
            "FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_ENDPOINT, or AZURE_OPENAI_ENDPOINT."
        )
    return endpoint.strip()


def _build_project_endpoint_from_parts() -> str | None:
    resource_name = os.getenv("FOUNDRY_RESOURCE_NAME")
    project_name = os.getenv("FOUNDRY_PROJECT_NAME")
    if resource_name and project_name:
        return f"https://{resource_name}.services.ai.azure.com/api/projects/{project_name}"
    return None


def _detect_endpoint_family(endpoint: str) -> Literal["foundry_project", "azure_openai"]:
    normalized = endpoint.rstrip("/")
    if ".services.ai.azure.com" in normalized:
        return "foundry_project"
    if ".openai.azure.com" in normalized:
        return "azure_openai"
    raise RuntimeError(
        "Unable to determine endpoint family from endpoint. Expected a Foundry project endpoint "
        "(.services.ai.azure.com) or Azure OpenAI endpoint (.openai.azure.com)."
    )


def _normalize_base_url(endpoint: str, endpoint_family: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/openai/v1"):
        return normalized
    if endpoint_family == "foundry_project":
        return f"{normalized}/openai/v1"
    return f"{normalized}/openai/v1"


def _resolve_openai_api_key(
    config: FoundryAuthConfig,
    *,
    api_key_override: Any | None = None,
) -> Any:
    if config.auth_mode == "api_key":
        api_key = api_key_override or os.getenv("FOUNDRY_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Legacy API-key auth requested, but neither FOUNDRY_API_KEY nor AZURE_OPENAI_API_KEY is set."
            )
        return api_key

    if get_bearer_token_provider is None:
        raise RuntimeError(
            "azure-identity is not installed. Run `uv sync --locked`, or set FOUNDRY_AUTH_MODE=api_key."
        )

    credential = build_credential()
    return get_bearer_token_provider(credential, config.scope)
