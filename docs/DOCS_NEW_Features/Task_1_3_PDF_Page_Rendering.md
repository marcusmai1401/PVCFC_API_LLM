# Task 1.3: PDF Page Image Rendering Pipeline

## Overview
Implement a robust pipeline for rendering specific PDF pages as images to support visual document navigation and page jump features.

## Objectives
1. Create a PDF page rendering module using PyMuPDF (fitz)
2. Implement caching mechanism for rendered pages
3. Provide API endpoints for page rendering
4. Support multiple image formats (PNG, JPEG)
5. Optimize for performance and memory usage

## Technical Requirements

### Core Components

#### 1. PDF Renderer Module (`tools/pdf_renderer.py`)
- **Functions:**
  - `render_page_to_image()`: Render specific page to image
  - `get_pdf_page_count()`: Get total pages in PDF
  - `validate_pdf_path()`: Validate PDF file existence and readability
  - `render_page_range()`: Render multiple pages at once
  - `get_page_thumbnail()`: Generate small preview thumbnails

- **Features:**
  - Support for different DPI settings (72, 150, 300)
  - Multiple image formats (PNG, JPEG, WEBP)
  - Page rotation handling
  - Error handling for corrupted PDFs
  - Memory-efficient processing for large PDFs

#### 2. Caching Layer
- **Cache Strategy:**
  - File-based caching in `artifacts/cache/pdf_pages/`
  - Cache key: `{pdf_hash}_{page_num}_{dpi}_{format}`
  - LRU eviction policy for memory cache
  - TTL for cached images (configurable)

- **Implementation:**
  - Use `cachetools` for in-memory caching
  - File system cache for persistent storage
  - Cache invalidation on PDF modification

#### 3. API Endpoints (`app/api/endpoints/pdf_renderer.py`)
- **Endpoints:**
  - `GET /api/pdf/render-page`: Render single page
  - `GET /api/pdf/page-count`: Get total pages
  - `GET /api/pdf/render-range`: Render page range
  - `GET /api/pdf/thumbnail`: Get page thumbnail

- **Parameters:**
  - `pdf_path`: Path to PDF file
  - `page_num`: Page number (1-indexed)
  - `dpi`: Resolution (default: 150)
  - `format`: Image format (default: png)
  - `width`/`height`: Optional resize parameters

- **Response:**
  - Image binary data with appropriate content-type
  - Error responses with meaningful messages

## Implementation Plan

### Phase 1: Core Module Development
1. Create `pdf_renderer.py` with basic rendering functions
2. Implement error handling and validation
3. Add logging for debugging

### Phase 2: Caching Implementation
1. Set up file-based cache directory structure
2. Implement cache read/write operations
3. Add cache invalidation logic
4. Implement in-memory cache with LRU

### Phase 3: API Integration
1. Create FastAPI endpoints
2. Add request validation with Pydantic
3. Implement streaming response for large images
4. Add CORS support for frontend

### Phase 4: Testing
1. Unit tests for renderer module
2. Cache performance tests
3. API integration tests
4. Load testing with concurrent requests

### Phase 5: Optimization
1. Profile memory usage
2. Optimize image compression
3. Implement lazy loading
4. Add batch processing support

## Dependencies
- `pymupdf`: PDF rendering (already installed)
- `Pillow`: Image processing
- `cachetools`: In-memory caching (already installed)
- `fastapi`: API framework (already installed)

## Performance Targets
- Single page render: < 500ms for 150 DPI
- Cached page retrieval: < 50ms
- Memory usage: < 100MB for 10 concurrent renders
- Cache hit ratio: > 80% for common pages

## Error Handling
1. Invalid PDF path: Return 404
2. Page out of range: Return 400 with valid range
3. Corrupted PDF: Return 422 with error details
4. Memory limit exceeded: Queue or reject with 503
5. Cache errors: Fall back to direct rendering

## Security Considerations
1. Validate PDF paths to prevent directory traversal
2. Limit maximum DPI to prevent DoS
3. Rate limiting on API endpoints
4. Sanitize file names in cache keys
5. Maximum file size limits

## Testing Requirements
1. Test with various PDF types (text, images, mixed)
2. Test page range boundaries
3. Test concurrent rendering requests
4. Test cache invalidation
5. Test memory limits and cleanup
6. Test with corrupted/malformed PDFs

## Success Criteria
- [x] PDF pages can be rendered as images
- [x] Caching reduces repeated render time by >90%
- [x] API endpoints are responsive and reliable
- [x] Error handling is comprehensive
- [x] Memory usage stays within limits
- [x] All tests pass with >90% coverage

## Future Enhancements
1. WebP format support for better compression
2. Progressive image loading
3. PDF annotation overlay support
4. OCR integration for scanned pages
5. Batch pre-rendering for common documents
