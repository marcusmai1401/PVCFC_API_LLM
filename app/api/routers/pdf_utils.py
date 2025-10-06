"""
PDF Utilities Router - Phase 2 Day 13

Provides endpoints for:
- Rendering PDF pages to images
- Getting page dimensions/metadata
- Supporting UI bbox overlay rendering
"""
import logging
import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pdf", tags=["PDF Utilities"])


# ============= REQUEST/RESPONSE SCHEMAS =============


class PageRenderRequest(BaseModel):
    """Request schema for PDF page rendering"""

    doc_id: str = Field(..., description="Document identifier")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    dpi: int = Field(default=150, ge=72, le=300, description="Rendering DPI (72-300)")
    format: Literal["jpeg", "png"] = Field(default="jpeg", description="Image format")


class PageInfoRequest(BaseModel):
    """Request schema for page metadata"""

    doc_id: str = Field(..., description="Document identifier")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")


class PageInfoResponse(BaseModel):
    """Response schema for page metadata"""

    doc_id: str
    page: int
    width: float = Field(..., description="Page width in points (1/72 inch)")
    height: float = Field(..., description="Page height in points (1/72 inch)")
    width_px: int = Field(..., description="Page width in pixels at 72 DPI")
    height_px: int = Field(..., description="Page height in pixels at 72 DPI")
    rotation: int = Field(default=0, description="Page rotation in degrees")

    class Config:
        json_schema_extra = {
            "example": {
                "doc_id": "PVCFC-KT06101-datasheet-v1",
                "page": 12,
                "width": 595.0,
                "height": 842.0,
                "width_px": 595,
                "height_px": 842,
                "rotation": 0,
            }
        }


# ============= HELPER FUNCTIONS =============


def _get_pdf_path_from_doc_id(doc_id: str, request: Request) -> Optional[str]:
    """
    Get PDF file path from doc_id using app state doc_id_map

    Returns:
        PDF path or None if not found
    """
    try:
        if not hasattr(request.app.state, "doc_id_map"):
            logger.warning("doc_id_map not available in app state")
            return None

        doc_id_map = request.app.state.doc_id_map
        if doc_id not in doc_id_map:
            logger.warning(f"doc_id '{doc_id}' not found in doc_id_map")
            return None

        doc_info = doc_id_map[doc_id]

        # Handle both dict format (new) and string format (legacy)
        if isinstance(doc_info, dict):
            pdf_path = doc_info.get("pdf_path")
        elif isinstance(doc_info, str):
            pdf_path = doc_info
        else:
            logger.warning(f"Invalid doc_info format for '{doc_id}': {type(doc_info)}")
            return None

        if not pdf_path:
            logger.warning(f"No pdf_path found for doc_id '{doc_id}'")
            return None

        # Verify file exists
        if not Path(pdf_path).exists():
            logger.warning(f"PDF file not found: {pdf_path}")
            return None

        return pdf_path

    except Exception as e:
        logger.error(f"Error getting PDF path for doc_id '{doc_id}': {e}")
        return None


# ============= ENDPOINTS =============


@router.get(
    "/render",
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}}},
        400: {"description": "Bad Request"},
        404: {"description": "Document or page not found"},
        500: {"description": "Internal Server Error"},
    },
)
async def render_pdf_page(
    doc_id: str = Query(..., description="Document identifier"),
    page: int = Query(..., ge=1, description="Page number (1-indexed)"),
    dpi: int = Query(150, ge=72, le=300, description="Rendering DPI"),
    format: Literal["jpeg", "png"] = Query("jpeg", description="Image format"),
    request: Request = None,
) -> Response:
    """
    Render a PDF page to an image.

    This endpoint renders a specific page from a PDF document to an image format
    suitable for display in UI with bbox overlays.

    **Use Cases:**
    - Display PDF pages in web viewer
    - Support bbox overlay rendering
    - Preview citations in context

    **Caching:**
    - Rendered images are cached in `artifacts/cache/pdf_pages/`
    - Cache key includes: doc_id, page, dpi, format
    - Subsequent requests return cached images (fast)

    **Performance:**
    - 72 DPI: ~100-200ms (fast, lower quality)
    - 150 DPI: ~200-400ms (balanced, recommended)
    - 300 DPI: ~500-1000ms (slow, high quality)
    """
    start_time = time.time()

    try:
        # Get PDF path from doc_id
        pdf_path = _get_pdf_path_from_doc_id(doc_id, request)

        if not pdf_path:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{doc_id}' not found or PDF path not available",
            )

        # Import renderer
        from tools.pdf_renderer import get_pdf_page_count, render_page_to_image

        # Validate page number
        try:
            page_count = get_pdf_page_count(pdf_path)
            if page > page_count:
                raise HTTPException(
                    status_code=404,
                    detail=f"Page {page} not found (document has {page_count} pages)",
                )
        except Exception as e:
            logger.error(f"Error getting page count: {e}")
            # Continue anyway, render_page_to_image will validate

        # Render page
        try:
            image_bytes, metadata = render_page_to_image(
                pdf_path=pdf_path,
                page_num=page,
                dpi=dpi,
                image_format=format,
                return_metadata=True,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"PDF file not accessible: {Path(pdf_path).name}",
            )
        except Exception as e:
            logger.error(f"Error rendering page: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to render page: {str(e)[:100]}"
            )

        # Determine content type
        content_type = "image/jpeg" if format == "jpeg" else "image/png"

        # Log timing
        elapsed_ms = (time.time() - start_time) * 1000
        cache_status = "HIT" if metadata.get("from_cache", False) else "MISS"
        logger.info(
            f"Rendered {doc_id} p.{page} at {dpi} DPI "
            f"({format}, {len(image_bytes)} bytes, {elapsed_ms:.0f}ms, cache={cache_status})"
        )

        # Return image with appropriate headers
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 1 day
                "X-Render-Time-Ms": str(int(elapsed_ms)),
                "X-Cache-Status": cache_status,
                "X-Page-Count": str(metadata.get("page_count", "unknown")),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in render_pdf_page: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/page-info", response_model=PageInfoResponse)
async def get_page_info(
    req: PageInfoRequest,
    request: Request,
) -> PageInfoResponse:
    """
    Get page dimensions and metadata for accurate bbox coordinate conversion.

    **Use Cases:**
    - Convert normalized bbox coordinates (0-1) to pixel coordinates
    - Ensure bbox overlays align correctly with rendered page images
    - Handle different page sizes and orientations

    **Returns:**
    - Page dimensions in points (1/72 inch)
    - Page dimensions in pixels at 72 DPI (standard)
    - Page rotation (0, 90, 180, 270 degrees)

    **Example Conversion:**
    ```javascript
    // Given normalized bbox [0.1, 0.2, 0.6, 0.4]
    const pageInfo = await fetch('/api/v1/pdf/page-info', {...});
    const x0_px = bbox[0] * pageInfo.width_px;
    const y0_px = bbox[1] * pageInfo.height_px;
    const x1_px = bbox[2] * pageInfo.width_px;
    const y1_px = bbox[3] * pageInfo.height_px;
    ```
    """
    try:
        # Get PDF path
        pdf_path = _get_pdf_path_from_doc_id(req.doc_id, request)

        if not pdf_path:
            raise HTTPException(
                status_code=404, detail=f"Document '{req.doc_id}' not found"
            )

        # Import PyMuPDF
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise HTTPException(status_code=500, detail="PyMuPDF not available")

        # Open PDF and get page
        try:
            doc = fitz.open(pdf_path)

            # Validate page number
            if req.page < 1 or req.page > doc.page_count:
                doc.close()
                raise HTTPException(
                    status_code=404,
                    detail=f"Page {req.page} not found (document has {doc.page_count} pages)",
                )

            page = doc.load_page(req.page - 1)  # 0-indexed

            # Get page rect (dimensions in points)
            rect = page.rect
            width = rect.width
            height = rect.height
            rotation = page.rotation

            # Calculate pixel dimensions at 72 DPI (standard)
            width_px = int(width)
            height_px = int(height)

            doc.close()

            logger.debug(
                f"Page info for {req.doc_id} p.{req.page}: "
                f"{width:.1f}x{height:.1f} pt ({width_px}x{height_px} px)"
            )

            return PageInfoResponse(
                doc_id=req.doc_id,
                page=req.page,
                width=width,
                height=height,
                width_px=width_px,
                height_px=height_px,
                rotation=rotation,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error reading page info: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to read page info: {str(e)[:100]}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_page_info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
