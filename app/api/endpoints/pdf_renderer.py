"""
PDF Rendering API Endpoints

Provides REST API endpoints for rendering PDF pages as images.
"""

import base64
import io
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from tools.pdf_renderer import (
    PDFRenderer,
    clear_cache,
    get_cache_stats,
    get_page_thumbnail,
    get_pdf_page_count,
    render_page_to_image,
    validate_pdf_path,
)

router = APIRouter(prefix="/api/pdf", tags=["PDF Rendering"])

# Initialize renderer
pdf_renderer = PDFRenderer()


class PDFInfo(BaseModel):
    """PDF document information"""

    pdf_path: str
    page_count: int
    is_valid: bool
    error_message: Optional[str] = None


class RenderPageRequest(BaseModel):
    """Request model for page rendering"""

    pdf_path: str = Field(..., description="Path to PDF file")
    page_num: int = Field(..., ge=1, description="Page number (1-indexed)")
    dpi: int = Field(150, ge=72, le=300, description="Resolution in DPI")
    format: str = Field("png", description="Output format: png, jpeg, jpg")
    use_cache: bool = Field(True, description="Use caching")


class RenderPageResponse(BaseModel):
    """Response model for page rendering metadata"""

    pdf_path: str
    page_num: int
    total_pages: int
    dpi: int
    format: str
    width: int
    height: int
    size_bytes: int
    image_data: Optional[str] = Field(None, description="Base64 encoded image data")


class ThumbnailRequest(BaseModel):
    """Request model for thumbnail generation"""

    pdf_path: str = Field(..., description="Path to PDF file")
    page_num: int = Field(..., ge=1, description="Page number (1-indexed)")
    max_width: int = Field(200, ge=50, le=800, description="Maximum thumbnail width")
    max_height: int = Field(200, ge=50, le=800, description="Maximum thumbnail height")
    format: str = Field("jpeg", description="Output format: png, jpeg, jpg")


class CacheStats(BaseModel):
    """Cache statistics"""

    memory_cache_size: int
    memory_cache_max_size: int
    file_cache_count: int
    file_cache_size_mb: float
    cache_directory: str


@router.get("/open")
async def open_pdf_in_browser(
    pdf_path: str = Query(..., description="Path to PDF file"),
    page: int = Query(default=1, ge=1, description="Page number to open (1-indexed)"),
):
    """
    Stream PDF file for viewing in browser with ability to jump to specific page.

    The browser will open the PDF viewer and jump to the specified page using
    the PDF fragment identifier (#page=N).

    **Use Cases:**
    - Direct PDF viewing with page navigation
    - IEEE-style citation links that open at exact page
    - Better UX than image rendering for multi-page viewing

    **Browser Support:**
    - Chrome/Edge: Full support for #page=N fragment
    - Firefox: Full support
    - Safari: Partial support (may need plugin)
    """
    try:
        # Validate PDF path
        is_valid, error_msg = validate_pdf_path(pdf_path)
        if not is_valid:
            raise HTTPException(status_code=404, detail=error_msg)

        # Verify file exists
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise HTTPException(
                status_code=404, detail=f"PDF file not found: {pdf_file.name}"
            )

        # Validate page number
        page_count = get_pdf_page_count(pdf_path)
        if page > page_count:
            logger.warning(
                f"Requested page {page} exceeds page count {page_count}, opening at page 1"
            )
            page = 1

        # Read PDF file
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        except Exception as e:
            logger.error(f"Error reading PDF file: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to read PDF file: {str(e)[:100]}"
            )

        # Log the request
        logger.info(
            f"Streaming PDF: {pdf_file.name} ({len(pdf_bytes)} bytes, page {page}/{page_count})"
        )

        # Return PDF with inline disposition so browser opens it
        # Browser will use #page=N fragment from URL to jump to page
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{pdf_file.name}"',
                "X-Page-Number": str(page),
                "X-Total-Pages": str(page_count),
                "Cache-Control": "public, max-age=86400",  # Cache for 1 day
                "Accept-Ranges": "bytes",  # Support range requests for large PDFs
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in open_pdf_in_browser: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/info", response_model=PDFInfo)
async def get_pdf_info(pdf_path: str = Query(..., description="Path to PDF file")):
    """
    Get PDF document information including page count.
    """
    try:
        is_valid, error_msg = validate_pdf_path(pdf_path)

        if not is_valid:
            return PDFInfo(
                pdf_path=pdf_path, page_count=0, is_valid=False, error_message=error_msg
            )

        page_count = get_pdf_page_count(pdf_path)

        return PDFInfo(
            pdf_path=pdf_path, page_count=page_count, is_valid=True, error_message=None
        )
    except Exception as e:
        logger.error(f"Error getting PDF info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/page-count")
async def get_page_count(pdf_path: str = Query(..., description="Path to PDF file")):
    """
    Get the total number of pages in a PDF document.
    """
    try:
        is_valid, error_msg = validate_pdf_path(pdf_path)

        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        page_count = get_pdf_page_count(pdf_path)
        return {"pdf_path": pdf_path, "page_count": page_count}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting page count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/render-page")
async def render_page(
    pdf_path: str = Query(..., description="Path to PDF file"),
    page_num: int = Query(..., ge=1, description="Page number (1-indexed)"),
    dpi: int = Query(150, ge=72, le=300, description="Resolution in DPI"),
    format: str = Query("png", description="Output format: png, jpeg, jpg"),
    use_cache: bool = Query(True, description="Use caching"),
):
    """
    Render a specific page of a PDF document as an image.
    Returns the image as binary data with appropriate content type.
    """
    try:
        # Validate PDF path
        is_valid, error_msg = validate_pdf_path(pdf_path)
        if not is_valid:
            raise HTTPException(status_code=404, detail=error_msg)

        # Validate page number
        page_count = get_pdf_page_count(pdf_path)
        if page_num > page_count:
            raise HTTPException(
                status_code=400,
                detail=f"Page {page_num} out of range. PDF has {page_count} pages",
            )

        # Render the page
        image_data, metadata = render_page_to_image(
            pdf_path, page_num, dpi, format, use_cache
        )

        # Determine content type
        content_type = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "webp": "image/webp",
        }.get(format.lower(), "application/octet-stream")

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(image_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=page_{page_num}.{format}",
                "X-Page-Number": str(page_num),
                "X-Total-Pages": str(metadata["total_pages"]),
                "X-Image-Width": str(metadata["width"]),
                "X-Image-Height": str(metadata["height"]),
            },
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error rendering page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/render-page", response_model=RenderPageResponse)
async def render_page_post(request: RenderPageRequest):
    """
    Render a specific page of a PDF document as an image (POST method).
    Returns metadata and optionally base64 encoded image data.
    """
    try:
        # Validate PDF path
        is_valid, error_msg = validate_pdf_path(request.pdf_path)
        if not is_valid:
            raise HTTPException(status_code=404, detail=error_msg)

        # Render the page
        image_data, metadata = render_page_to_image(
            request.pdf_path,
            request.page_num,
            request.dpi,
            request.format,
            request.use_cache,
        )

        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        return RenderPageResponse(
            pdf_path=metadata["pdf_path"],
            page_num=metadata["page_num"],
            total_pages=metadata["total_pages"],
            dpi=metadata["dpi"],
            format=metadata["format"],
            width=metadata["width"],
            height=metadata["height"],
            size_bytes=metadata["size_bytes"],
            image_data=image_base64,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error rendering page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/render-range")
async def render_page_range(
    pdf_path: str = Query(..., description="Path to PDF file"),
    start_page: int = Query(..., ge=1, description="Start page number"),
    end_page: int = Query(..., ge=1, description="End page number"),
    dpi: int = Query(150, ge=72, le=300, description="Resolution in DPI"),
    format: str = Query("png", description="Output format"),
    use_cache: bool = Query(True, description="Use caching"),
):
    """
    Render a range of PDF pages.
    Returns metadata for all rendered pages.
    """
    try:
        # Validate inputs
        is_valid, error_msg = validate_pdf_path(pdf_path)
        if not is_valid:
            raise HTTPException(status_code=404, detail=error_msg)

        if start_page > end_page:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid range: start_page ({start_page}) > end_page ({end_page})",
            )

        # Limit range to prevent DoS
        max_range = 10
        if end_page - start_page + 1 > max_range:
            raise HTTPException(
                status_code=400,
                detail=f"Range too large. Maximum {max_range} pages at once",
            )

        # Render pages
        results = []
        for page_num in range(start_page, end_page + 1):
            try:
                image_data, metadata = render_page_to_image(
                    pdf_path, page_num, dpi, format, use_cache
                )
                results.append(
                    {
                        "page_num": page_num,
                        "width": metadata["width"],
                        "height": metadata["height"],
                        "size_bytes": metadata["size_bytes"],
                    }
                )
            except Exception as e:
                results.append({"page_num": page_num, "error": str(e)})

        return {
            "pdf_path": pdf_path,
            "start_page": start_page,
            "end_page": end_page,
            "dpi": dpi,
            "format": format,
            "pages": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rendering page range: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thumbnail")
async def get_thumbnail(
    pdf_path: str = Query(..., description="Path to PDF file"),
    page_num: int = Query(..., ge=1, description="Page number"),
    max_width: int = Query(200, ge=50, le=800, description="Maximum width"),
    max_height: int = Query(200, ge=50, le=800, description="Maximum height"),
    format: str = Query("jpeg", description="Output format"),
):
    """
    Generate a thumbnail for a PDF page.
    """
    try:
        # Validate PDF
        is_valid, error_msg = validate_pdf_path(pdf_path)
        if not is_valid:
            raise HTTPException(status_code=404, detail=error_msg)

        # Generate thumbnail
        thumb_data, metadata = get_page_thumbnail(
            pdf_path, page_num, max_width, max_height, format
        )

        # Determine content type
        content_type = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
        }.get(format.lower(), "application/octet-stream")

        return StreamingResponse(
            io.BytesIO(thumb_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=thumb_page_{page_num}.{format}",
                "X-Thumbnail-Width": str(metadata["thumb_width"]),
                "X-Thumbnail-Height": str(metadata["thumb_height"]),
            },
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/thumbnail")
async def create_thumbnail(request: ThumbnailRequest):
    """
    Generate a thumbnail for a PDF page (POST method).
    Returns base64 encoded thumbnail data.
    """
    try:
        # Generate thumbnail
        thumb_data, metadata = get_page_thumbnail(
            request.pdf_path,
            request.page_num,
            request.max_width,
            request.max_height,
            request.format,
        )

        # Encode to base64
        thumb_base64 = base64.b64encode(thumb_data).decode("utf-8")

        return {
            "pdf_path": request.pdf_path,
            "page_num": request.page_num,
            "thumbnail_width": metadata["thumb_width"],
            "thumbnail_height": metadata["thumb_height"],
            "format": request.format,
            "size_bytes": metadata["size_bytes"],
            "thumbnail_data": thumb_base64,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats", response_model=CacheStats)
async def get_cache_statistics():
    """
    Get cache statistics.
    """
    try:
        stats = get_cache_stats()
        return CacheStats(**stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
async def clear_pdf_cache(
    pdf_path: Optional[str] = Query(None, description="Specific PDF to clear cache for")
):
    """
    Clear cache for a specific PDF or all PDFs.
    """
    try:
        if pdf_path:
            # Validate PDF exists
            is_valid, error_msg = validate_pdf_path(pdf_path)
            if not is_valid:
                raise HTTPException(status_code=404, detail=error_msg)

            clear_cache(pdf_path)
            return {"message": f"Cache cleared for {pdf_path}"}
        else:
            clear_cache()
            return {"message": "All cache cleared"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint for PDF rendering service.
    """
    try:
        stats = get_cache_stats()
        return {"status": "healthy", "service": "PDF Renderer", "cache_stats": stats}
    except Exception as e:
        return {"status": "unhealthy", "service": "PDF Renderer", "error": str(e)}
