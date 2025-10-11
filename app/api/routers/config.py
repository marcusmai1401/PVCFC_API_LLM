"""
Config management endpoint for runtime configuration updates
"""
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from app.core.config import settings
from app.deps.indices import get_index_manager

router = APIRouter(prefix="/config", tags=["Configuration"])


class RetrieverModeUpdate(BaseModel):
    """Request model for updating retriever mode"""

    mode: str  # "faiss" or "weaviate"


class ConfigUpdateResponse(BaseModel):
    """Response model for config updates"""

    success: bool
    message: str
    current_mode: str
    requires_restart: bool


@router.get("/retriever-mode")
async def get_retriever_mode(request: Request) -> Dict[str, Any]:
    """
    Get current retriever mode (FAISS or Weaviate)

    Returns:
        - mode: "faiss" or "weaviate"
        - weaviate_enabled: bool
        - retriever_type: current active retriever
    """
    try:
        # Get from index manager
        manager = get_index_manager()
        retriever_type = manager.retriever_type or "unknown"

        return {
            "mode": retriever_type,
            "weaviate_enabled": settings.weaviate_enabled,
            "retriever_type": retriever_type,
            "can_switch_to_weaviate": True,  # Could add Weaviate availability check
            "can_switch_to_faiss": True,
        }
    except Exception as e:
        logger.error(f"Failed to get retriever mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retriever-mode", response_model=ConfigUpdateResponse)
async def update_retriever_mode(
    update: RetrieverModeUpdate, request: Request
) -> ConfigUpdateResponse:
    """
    Update retriever mode (FAISS or Weaviate)

    This updates the .env file and marks that API restart is required.

    Args:
        update: Mode to switch to ("faiss" or "weaviate")

    Returns:
        Success status and instructions
    """
    try:
        target_mode = update.mode.lower()

        if target_mode not in ["faiss", "weaviate"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {target_mode}. Must be 'faiss' or 'weaviate'",
            )

        # Get current mode
        manager = get_index_manager()
        current_mode = manager.retriever_type or "unknown"

        if current_mode == target_mode:
            return ConfigUpdateResponse(
                success=True,
                message=f"Already using {target_mode} mode",
                current_mode=current_mode,
                requires_restart=False,
            )

        # Update .env file
        env_file = Path(".env")
        if not env_file.exists():
            # Create from .env.example if not exists
            env_example = Path(".env.example")
            if env_example.exists():
                env_file.write_text(env_example.read_text(encoding="utf-8"))
            else:
                # Create minimal .env
                env_file.write_text("", encoding="utf-8")

        # Read current .env
        env_lines = env_file.read_text(encoding="utf-8").splitlines()

        # Update or add WEAVIATE_ENABLED
        weaviate_enabled_value = "true" if target_mode == "weaviate" else "false"
        updated_lines = []
        found = False

        for line in env_lines:
            if line.startswith("WEAVIATE_ENABLED="):
                updated_lines.append(f"WEAVIATE_ENABLED={weaviate_enabled_value}")
                found = True
            else:
                updated_lines.append(line)

        if not found:
            # Add at the end
            updated_lines.append(f"\n# Phase 4 - Weaviate Configuration")
            updated_lines.append(f"WEAVIATE_ENABLED={weaviate_enabled_value}")

        # Write back
        env_file.write_text("\n".join(updated_lines), encoding="utf-8")

        logger.info(
            f"Updated .env: WEAVIATE_ENABLED={weaviate_enabled_value} (switched to {target_mode} mode)"
        )

        return ConfigUpdateResponse(
            success=True,
            message=f"Configuration updated to {target_mode} mode. Please restart the API for changes to take effect.",
            current_mode=current_mode,
            requires_restart=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update retriever mode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")


@router.get("/current")
async def get_current_config(request: Request) -> Dict[str, Any]:
    """
    Get current runtime configuration

    Returns:
        Current settings and retriever info
    """
    try:
        manager = get_index_manager()

        return {
            "retriever_type": manager.retriever_type or "unknown",
            "weaviate_enabled": settings.weaviate_enabled,
            "weaviate_host": settings.weaviate_host,
            "weaviate_port": settings.weaviate_port,
            "weaviate_collection": settings.weaviate_collection,
            "enable_bge_rerank": settings.enable_bge_rerank,
            "bge_rerank_top_k": settings.bge_rerank_top_k,
            "bge_rerank_level": settings.bge_rerank_level,
            "llm_provider": settings.llm_provider,
            "embedding_provider": settings.embedding_provider_effective(),
        }
    except Exception as e:
        logger.error(f"Failed to get current config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
