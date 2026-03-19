from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.config.settings import Settings, get_settings
from app.library import cache
from app.library.db import transaction
from app.models import llm_config_model
from app.services.activity_service import record_activity


ALLOWED_PROVIDERS = {'anthropic', 'openai', 'openai_compatible', 'gemini'}


@dataclass(frozen=True)
class RuntimeLLMConfig:
    id: str | None
    name: str
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    max_output_tokens: int
    temperature: float
    top_p: float
    reasoning_effort: str | None
    source: str
    metadata: dict

    def signature(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'provider': self.provider,
            'base_url': self.base_url,
            'api_key_hash': cache.build_hash(self.api_key or ''),
            'model': self.model,
            'timeout_seconds': self.timeout_seconds,
            'max_output_tokens': self.max_output_tokens,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'reasoning_effort': self.reasoning_effort,
            'source': self.source,
        }



def _normalize_string(value: str | None) -> str:
    return (value or '').strip()



def _mask_api_key(value: str | None) -> str | None:
    token = _normalize_string(value)
    if not token:
        return None
    if len(token) <= 8:
        return '*' * len(token)
    return f"{token[:4]}...{token[-4:]}"



def _serialize_config(row: dict) -> dict:
    return {
        'id': str(row['id']),
        'name': row['name'],
        'provider': row['provider'],
        'base_url': row.get('base_url') or '',
        'model': row['model'],
        'timeout_seconds': int(row['timeout_seconds']),
        'max_output_tokens': int(row['max_output_tokens']),
        'temperature': float(row['temperature']),
        'top_p': float(row['top_p']),
        'reasoning_effort': row.get('reasoning_effort'),
        'is_active': bool(row['is_active']),
        'is_enabled': bool(row['is_enabled']),
        'metadata': row.get('metadata') or {},
        'has_api_key': bool(_normalize_string(row.get('api_key'))),
        'api_key_masked': _mask_api_key(row.get('api_key')),
        'created_by': str(row['created_by']) if row.get('created_by') else None,
        'updated_by': str(row['updated_by']) if row.get('updated_by') else None,
        'created_at': row.get('created_at'),
        'updated_at': row.get('updated_at'),
    }



def _runtime_from_row(row: dict) -> RuntimeLLMConfig:
    return RuntimeLLMConfig(
        id=str(row['id']) if row.get('id') else None,
        name=row['name'],
        provider=row['provider'],
        base_url=_normalize_string(row.get('base_url')),
        api_key=_normalize_string(row.get('api_key')),
        model=row['model'],
        timeout_seconds=int(row['timeout_seconds']),
        max_output_tokens=int(row['max_output_tokens']),
        temperature=float(row['temperature']),
        top_p=float(row['top_p']),
        reasoning_effort=_normalize_string(row.get('reasoning_effort')) or None,
        source='database',
        metadata=row.get('metadata') or {},
    )



def _runtime_from_settings(settings: Settings) -> RuntimeLLMConfig:
    return RuntimeLLMConfig(
        id=None,
        name='Environment Default',
        provider=settings.llm_provider,
        base_url=_normalize_string(settings.llm_base_url),
        api_key=_normalize_string(settings.llm_api_key),
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
        temperature=settings.llm_temperature,
        top_p=settings.llm_top_p,
        reasoning_effort=settings.llm_reasoning_effort,
        source='environment',
        metadata={'seeded_from': 'environment'},
    )



def _validate_payload(*, provider: str, base_url: str | None, api_key: str | None, model: str, is_enabled: bool) -> tuple[str, str, str, str]:
    normalized_provider = _normalize_string(provider)
    normalized_base_url = _normalize_string(base_url)
    normalized_api_key = _normalize_string(api_key)
    normalized_model = _normalize_string(model)

    if normalized_provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported LLM provider.')
    if not normalized_model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Model name is required.')
    if normalized_provider == 'openai_compatible' and not normalized_base_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Base URL is required for openai_compatible provider.')
    if normalized_provider in {'anthropic', 'openai', 'gemini'} and not normalized_api_key and is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='API key is required for enabled cloud providers.')
    return normalized_provider, normalized_base_url, normalized_api_key, normalized_model



def _bump_llm_version() -> int:
    return cache.incr(cache.LLM_CONFIG_VERSION_KEY)



def ensure_default_llm_config(*, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    try:
        if llm_config_model.count_llm_configs() > 0 and llm_config_model.get_active_llm_config():
            return
        with transaction() as conn:
            count = llm_config_model.count_llm_configs(conn=conn)
            active = llm_config_model.get_active_llm_config(conn=conn)
            if count > 0 and active:
                return
            default_runtime = _runtime_from_settings(resolved)
            if count == 0:
                llm_config_model.create_llm_config(
                    name=default_runtime.name,
                    provider=default_runtime.provider,
                    base_url=default_runtime.base_url or None,
                    api_key=default_runtime.api_key or None,
                    model=default_runtime.model,
                    timeout_seconds=default_runtime.timeout_seconds,
                    max_output_tokens=default_runtime.max_output_tokens,
                    temperature=default_runtime.temperature,
                    top_p=default_runtime.top_p,
                    reasoning_effort=default_runtime.reasoning_effort,
                    is_active=True,
                    is_enabled=True,
                    metadata=default_runtime.metadata,
                    created_by=None,
                    updated_by=None,
                    conn=conn,
                )
            elif not active:
                configs = llm_config_model.list_llm_configs(conn=conn)
                first_enabled = next((item for item in configs if item.get('is_enabled')), None)
                if first_enabled:
                    llm_config_model.deactivate_all_llm_configs(updated_by=None, conn=conn)
                    llm_config_model.activate_llm_config(first_enabled['id'], updated_by=None, conn=conn)
                else:
                    llm_config_model.create_llm_config(
                        name=default_runtime.name,
                        provider=default_runtime.provider,
                        base_url=default_runtime.base_url or None,
                        api_key=default_runtime.api_key or None,
                        model=default_runtime.model,
                        timeout_seconds=default_runtime.timeout_seconds,
                        max_output_tokens=default_runtime.max_output_tokens,
                        temperature=default_runtime.temperature,
                        top_p=default_runtime.top_p,
                        reasoning_effort=default_runtime.reasoning_effort,
                        is_active=True,
                        is_enabled=True,
                        metadata=default_runtime.metadata,
                        created_by=None,
                        updated_by=None,
                        conn=conn,
                    )
        _bump_llm_version()
    except Exception:
        # Runtime fallback to environment config remains available if the table is not ready yet.
        return



def list_llm_configs() -> dict:
    ensure_default_llm_config()
    items = [_serialize_config(item) for item in llm_config_model.list_llm_configs()]
    active = next((item for item in items if item['is_active']), None)
    return {'items': items, 'active_config_id': active['id'] if active else None}



def get_active_llm_config_snapshot() -> dict:
    ensure_default_llm_config()
    active = llm_config_model.get_active_llm_config()
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No active LLM configuration is available.')
    return _serialize_config(active)



def create_llm_config(*, payload, current_user: dict) -> dict:
    provider, base_url, api_key, model = _validate_payload(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        model=payload.model,
        is_enabled=payload.is_enabled,
    )
    with transaction() as conn:
        if payload.activate:
            llm_config_model.deactivate_all_llm_configs(updated_by=UUID(str(current_user['id'])), conn=conn)
        created = llm_config_model.create_llm_config(
            name=payload.name.strip(),
            provider=provider,
            base_url=base_url or None,
            api_key=api_key or None,
            model=model,
            timeout_seconds=payload.timeout_seconds,
            max_output_tokens=payload.max_output_tokens,
            temperature=payload.temperature,
            top_p=payload.top_p,
            reasoning_effort=_normalize_string(payload.reasoning_effort) or None,
            is_active=payload.activate,
            is_enabled=payload.is_enabled,
            metadata=payload.metadata,
            created_by=UUID(str(current_user['id'])),
            updated_by=UUID(str(current_user['id'])),
            conn=conn,
        )
        record_activity(
            actor_user_id=UUID(str(current_user['id'])),
            activity_type='admin.llm_config.created',
            target_type='llm_config',
            target_id=UUID(str(created['id'])) if created else None,
            description=f"Admin created LLM config '{payload.name.strip()}'.",
            visibility='foreground',
            metadata={'provider': provider, 'model': model, 'activated': payload.activate},
            conn=conn,
        )
    _bump_llm_version()
    return _serialize_config(created)



def update_llm_config(*, config_id: UUID, payload, current_user: dict) -> dict:
    existing = llm_config_model.get_llm_config(config_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='LLM config not found.')

    api_key = existing.get('api_key')
    if payload.clear_api_key:
        api_key = ''
    elif payload.api_key is not None:
        api_key = payload.api_key

    provider, base_url, normalized_api_key, model = _validate_payload(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=api_key,
        model=payload.model,
        is_enabled=payload.is_enabled,
    )

    with transaction() as conn:
        updated = llm_config_model.update_llm_config(
            config_id=config_id,
            name=payload.name.strip(),
            provider=provider,
            base_url=base_url or None,
            api_key=normalized_api_key or None,
            model=model,
            timeout_seconds=payload.timeout_seconds,
            max_output_tokens=payload.max_output_tokens,
            temperature=payload.temperature,
            top_p=payload.top_p,
            reasoning_effort=_normalize_string(payload.reasoning_effort) or None,
            is_enabled=payload.is_enabled,
            metadata=payload.metadata,
            updated_by=UUID(str(current_user['id'])),
            conn=conn,
        )
        if payload.activate or (existing.get('is_active') and not payload.is_enabled):
            llm_config_model.deactivate_all_llm_configs(updated_by=UUID(str(current_user['id'])), conn=conn)
            if payload.is_enabled:
                updated = llm_config_model.activate_llm_config(config_id, updated_by=UUID(str(current_user['id'])), conn=conn)
        record_activity(
            actor_user_id=UUID(str(current_user['id'])),
            activity_type='admin.llm_config.updated',
            target_type='llm_config',
            target_id=config_id,
            description=f"Admin updated LLM config '{payload.name.strip()}'.",
            visibility='foreground',
            metadata={'provider': provider, 'model': model, 'activated': payload.activate},
            conn=conn,
        )
    _bump_llm_version()
    return _serialize_config(updated)



def activate_llm_config(*, config_id: UUID, current_user: dict) -> dict:
    existing = llm_config_model.get_llm_config(config_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='LLM config not found.')
    if not existing.get('is_enabled'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only enabled configs can be activated.')

    with transaction() as conn:
        llm_config_model.deactivate_all_llm_configs(updated_by=UUID(str(current_user['id'])), conn=conn)
        activated = llm_config_model.activate_llm_config(config_id, updated_by=UUID(str(current_user['id'])), conn=conn)
        record_activity(
            actor_user_id=UUID(str(current_user['id'])),
            activity_type='admin.llm_config.activated',
            target_type='llm_config',
            target_id=config_id,
            description=f"Admin activated LLM config '{existing['name']}'.",
            visibility='foreground',
            metadata={'provider': existing['provider'], 'model': existing['model']},
            conn=conn,
        )
    _bump_llm_version()
    return _serialize_config(activated)



def delete_llm_config(*, config_id: UUID, current_user: dict) -> dict:
    existing = llm_config_model.get_llm_config(config_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='LLM config not found.')
    all_configs = llm_config_model.list_llm_configs()
    if len(all_configs) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='At least one LLM config must remain available.')
    if existing.get('is_active'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Activate another LLM config before deleting the current active one.')

    with transaction() as conn:
        llm_config_model.delete_llm_config(config_id, conn=conn)
        record_activity(
            actor_user_id=UUID(str(current_user['id'])),
            activity_type='admin.llm_config.deleted',
            target_type='llm_config',
            target_id=config_id,
            description=f"Admin deleted LLM config '{existing['name']}'.",
            visibility='foreground',
            metadata={'provider': existing['provider'], 'model': existing['model']},
            conn=conn,
        )
    _bump_llm_version()
    return {'deleted_count': 1, 'deleted_ids': [str(config_id)]}



def get_active_runtime_config(*, settings: Settings | None = None) -> RuntimeLLMConfig:
    resolved = settings or get_settings()
    ensure_default_llm_config(settings=resolved)
    try:
        active = llm_config_model.get_active_llm_config()
        if not active:
            return _runtime_from_settings(resolved)
        return _runtime_from_row(active)
    except Exception:
        return _runtime_from_settings(resolved)
