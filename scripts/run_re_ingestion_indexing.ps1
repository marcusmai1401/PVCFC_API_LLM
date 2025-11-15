# Script tự động hóa quá trình Re-Ingestion & Indexing theo Pipeline Mới
# Version: 1.0
# Date: 2025-01-XX

param(
    [string]$SourceDir = "D:\Data_Raw",
    [string]$OutputDir = "artifacts\ingestion_production",
    [int]$Workers = 2,
    [switch]$SkipBackup,
    [switch]$SkipIngestion,
    [switch]$SkipIndexing,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "RE-INGESTION & INDEXING - PIPELINE MỚI" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# BƯỚC 0: KIỂM TRA TIỀN ĐIỀU KIỆN
# ============================================

Write-Host "[0/7] Kiểm tra tiền điều kiện..." -ForegroundColor Yellow

# Check virtual environment
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "✗ Virtual environment không tồn tại!" -ForegroundColor Red
    Write-Host "  Chạy: py -3.11 -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Check .env file
if (-not (Test-Path ".env")) {
    Write-Host "✗ File .env không tồn tại!" -ForegroundColor Red
    Write-Host "  Copy từ .env.example và cấu hình" -ForegroundColor Yellow
    exit 1
}

# Check ENABLE_PID_TAGS
$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch "ENABLE_PID_TAGS\s*=\s*true") {
    Write-Host "⚠ ENABLE_PID_TAGS chưa set = true trong .env" -ForegroundColor Yellow
    Write-Host "  Đề xuất: Thêm ENABLE_PID_TAGS=true vào .env" -ForegroundColor Yellow
    if (-not $Force) {
        $response = Read-Host "  Tiếp tục? (y/N)"
        if ($response -ne "y") { exit 1 }
    }
}

# Check GOOGLE_APPLICATION_CREDENTIALS
$googleCreds = [System.Environment]::GetEnvironmentVariable("GOOGLE_APPLICATION_CREDENTIALS", "Process")
if ([string]::IsNullOrEmpty($googleCreds)) {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "GOOGLE_APPLICATION_CREDENTIALS\s*=\s*(.+)") {
        $googleCreds = $matches[1].Trim()
    }
}
if ([string]::IsNullOrEmpty($googleCreds) -or -not (Test-Path $googleCreds)) {
    Write-Host "⚠ GOOGLE_APPLICATION_CREDENTIALS chưa set hoặc file không tồn tại" -ForegroundColor Yellow
    Write-Host "  Cần set để dùng Google Cloud Vision API" -ForegroundColor Yellow
    if (-not $Force) {
        $response = Read-Host "  Tiếp tục? (y/N)"
        if ($response -ne "y") { exit 1 }
    }
}

# Check source directory
if (-not (Test-Path $SourceDir)) {
    Write-Host "✗ Source directory không tồn tại: $SourceDir" -ForegroundColor Red
    exit 1
}
$pdfCount = (Get-ChildItem $SourceDir -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue).Count
if ($pdfCount -eq 0) {
    Write-Host "⚠ Không tìm thấy PDF files trong: $SourceDir" -ForegroundColor Yellow
    if (-not $Force) {
        $response = Read-Host "  Tiếp tục? (y/N)"
        if ($response -ne "y") { exit 1 }
    }
} else {
    Write-Host "✓ Tìm thấy $pdfCount PDF files" -ForegroundColor Green
}

# Check OpenSearch
try {
    $osResponse = Invoke-RestMethod -Uri "http://localhost:9200" -TimeoutSec 5
    Write-Host "✓ OpenSearch đang chạy" -ForegroundColor Green
} catch {
    Write-Host "✗ OpenSearch không chạy hoặc không kết nối được" -ForegroundColor Red
    Write-Host "  Chạy: docker-compose up -d opensearch" -ForegroundColor Yellow
    exit 1
}

# Check Weaviate
try {
    $wvResponse = Invoke-RestMethod -Uri "http://localhost:8080/v1/.well-known/ready" -TimeoutSec 5
    if ($wvResponse.ready) {
        Write-Host "✓ Weaviate đang chạy" -ForegroundColor Green
    } else {
        Write-Host "✗ Weaviate chưa ready" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ Weaviate không chạy hoặc không kết nối được" -ForegroundColor Red
    Write-Host "  Chạy: docker-compose up -d weaviate" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Tất cả tiền điều kiện đã thỏa mãn" -ForegroundColor Green
Write-Host ""

# ============================================
# BƯỚC 1: BACKUP DỮ LIỆU CŨ
# ============================================

if (-not $SkipBackup) {
    Write-Host "[1/7] Backup dữ liệu cũ..." -ForegroundColor Yellow

    $backupDir = "artifacts\backup_before_reingestion_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

    $backedUp = $false

    if (Test-Path "artifacts\ingestion_production") {
        Write-Host "  Backing up ingestion_production..." -ForegroundColor Cyan
        Copy-Item -Path "artifacts\ingestion_production" -Destination "$backupDir\ingestion_production" -Recurse -ErrorAction SilentlyContinue
        $backedUp = $true
    }

    if (Test-Path "artifacts\index_production") {
        Write-Host "  Backing up index_production..." -ForegroundColor Cyan
        Copy-Item -Path "artifacts\index_production" -Destination "$backupDir\index_production" -Recurse -ErrorAction SilentlyContinue
        $backedUp = $true
    }

    if ($backedUp) {
        Write-Host "✓ Backup hoàn tất: $backupDir" -ForegroundColor Green
    } else {
        Write-Host "⚠ Không có dữ liệu cũ để backup" -ForegroundColor Yellow
    }

    Write-Host ""
} else {
    Write-Host "[1/7] Skip backup (--SkipBackup)" -ForegroundColor Gray
    Write-Host ""
}

# ============================================
# BƯỚC 2: TẠO/RESET OPENSEARCH INDEXES
# ============================================

Write-Host "[2/7] Tạo/Reset OpenSearch indexes..." -ForegroundColor Yellow

# Activate virtual environment
Write-Host "  Activating .venv..." -ForegroundColor Cyan
& ".venv\Scripts\Activate.ps1"

# Create rag_chunks index
Write-Host "  Tạo rag_chunks index..." -ForegroundColor Cyan
python scripts\opensearch\create_rag_chunks_index.py --delete-if-exists
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Lỗi khi tạo rag_chunks index" -ForegroundColor Red
    exit 1
}

# Create spatial_components index
Write-Host "  Tạo spatial_components index..." -ForegroundColor Cyan
python scripts\opensearch\create_spatial_components_index.py --delete-if-exists
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Lỗi khi tạo spatial_components index" -ForegroundColor Red
    exit 1
}

# Verify indexes
$indices = Invoke-RestMethod -Uri "http://localhost:9200/_cat/indices?v"
$ragChunksExists = $indices -match "rag_chunks"
$spatialExists = $indices -match "pvcfc_pid_spatial_components"

if ($ragChunksExists -and $spatialExists) {
    Write-Host "✓ Cả hai indexes đã được tạo thành công" -ForegroundColor Green
} else {
    Write-Host "✗ Một số indexes chưa được tạo" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================
# BƯỚC 3: CLEAR WEAVIATE COLLECTION (NẾU CẦN)
# ============================================

Write-Host "[3/7] Clear Weaviate collection..." -ForegroundColor Yellow

try {
    # Try to delete collection (will fail if doesn't exist, that's OK)
    $deleteBody = '{"class": "Chunk"}'
    try {
        Invoke-RestMethod -Method Delete -Uri "http://localhost:8080/v1/schema/Chunk" `
            -Headers @{"Content-Type" = "application/json"} -TimeoutSec 5 | Out-Null
        Write-Host "✓ Đã xóa collection cũ" -ForegroundColor Green
    } catch {
        Write-Host "  Collection chưa tồn tại (OK)" -ForegroundColor Gray
    }
} catch {
    Write-Host "⚠ Không thể clear collection (sẽ tạo mới khi index)" -ForegroundColor Yellow
}

Write-Host ""

# ============================================
# BƯỚC 4: RUN INGESTION
# ============================================

if (-not $SkipIngestion) {
    Write-Host "[4/7] Chạy ingestion..." -ForegroundColor Yellow
    Write-Host "  Source: $SourceDir" -ForegroundColor Cyan
    Write-Host "  Output: $OutputDir" -ForegroundColor Cyan
    Write-Host "  Workers: $Workers" -ForegroundColor Cyan
    Write-Host "  Đang chạy (có thể mất 2-10 giờ)..." -ForegroundColor Cyan
    Write-Host ""

    $ingestionStart = Get-Date

    python tools\ingest.py `
        --source-dir $SourceDir `
        --output-dir $OutputDir `
        --enable-ocr `
        --enable-pid-tags `
        --workers $Workers `
        --emit-jsonl

    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Lỗi khi chạy ingestion" -ForegroundColor Red
        exit 1
    }

    $ingestionEnd = Get-Date
    $ingestionDuration = $ingestionEnd - $ingestionStart
    Write-Host ""
    Write-Host "✓ Ingestion hoàn tất trong $($ingestionDuration.TotalMinutes.ToString('F2')) phút" -ForegroundColor Green

    # Verify outputs
    $chunksFile = "$OutputDir\chunks\chunks.jsonl"
    if (Test-Path $chunksFile) {
        $chunksCount = (Get-Content $chunksFile).Count
        Write-Host "✓ Tạo được $chunksCount chunks" -ForegroundColor Green
    } else {
        Write-Host "✗ Chunks file không tồn tại!" -ForegroundColor Red
        exit 1
    }

    if (Test-Path "$OutputDir\entities\tags.jsonl") {
        $tagsCount = (Get-Content "$OutputDir\entities\tags.jsonl").Count
        Write-Host "✓ Extract được $tagsCount P&ID tags" -ForegroundColor Green
    }

    Write-Host ""
} else {
    Write-Host "[4/7] Skip ingestion (--SkipIngestion)" -ForegroundColor Gray
    Write-Host ""
}

# ============================================
# BƯỚC 5: INDEX CHUNKS VÀO OPENSEARCH & WEAVIATE
# ============================================

if (-not $SkipIndexing) {
    Write-Host "[5/7] Index chunks vào OpenSearch & Weaviate..." -ForegroundColor Yellow
    Write-Host "  Đang chạy (có thể mất 35-40 phút)..." -ForegroundColor Cyan
    Write-Host ""

    $indexingStart = Get-Date

    python scripts\utilities\index_production_chunks.py

    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Lỗi khi index chunks" -ForegroundColor Red
        exit 1
    }

    $indexingEnd = Get-Date
    $indexingDuration = $indexingEnd - $indexingStart
    Write-Host ""
    Write-Host "✓ Indexing hoàn tất trong $($indexingDuration.TotalMinutes.ToString('F2')) phút" -ForegroundColor Green

    Write-Host ""
} else {
    Write-Host "[5/7] Skip indexing (--SkipIndexing)" -ForegroundColor Gray
    Write-Host ""
}

# ============================================
# BƯỚC 6: VERIFY INDEXES
# ============================================

Write-Host "[6/7] Kiểm tra indexes..." -ForegroundColor Yellow

# OpenSearch rag_chunks
try {
    $ragChunksCount = (Invoke-RestMethod -Uri "http://localhost:9200/rag_chunks/_count").count
    Write-Host "✓ OpenSearch rag_chunks: $ragChunksCount documents" -ForegroundColor Green
} catch {
    Write-Host "✗ Không thể đếm rag_chunks" -ForegroundColor Red
}

# OpenSearch spatial_components
try {
    $componentsCount = (Invoke-RestMethod -Uri "http://localhost:9200/pvcfc_pid_spatial_components/_count").count
    Write-Host "✓ OpenSearch spatial_components: $componentsCount components" -ForegroundColor Green
} catch {
    Write-Host "⚠ Không thể đếm spatial_components (có thể không có P&ID docs)" -ForegroundColor Yellow
}

# Weaviate
try {
    $wvBody = '{ "query": "{ Aggregate { Chunk { meta { count } } } }" }'
    $wvResult = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/v1/graphql" `
        -Headers @{"Content-Type" = "application/json"} `
        -Body $wvBody -TimeoutSec 10
    $wvCount = $wvResult.data.Aggregate.Chunk[0].meta.count
    Write-Host "✓ Weaviate Chunk: $wvCount objects" -ForegroundColor Green
} catch {
    Write-Host "✗ Không thể đếm Weaviate objects" -ForegroundColor Red
}

Write-Host ""

# ============================================
# BƯỚC 7: TÓM TẮT
# ============================================

Write-Host "[7/7] Tóm tắt..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "HOÀN TẤT RE-INGESTION & INDEXING" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Kết quả:" -ForegroundColor Green
Write-Host "  - OpenSearch rag_chunks: $ragChunksCount documents" -ForegroundColor White
Write-Host "  - OpenSearch spatial_components: $componentsCount components" -ForegroundColor White
Write-Host "  - Weaviate Chunk: $wvCount objects" -ForegroundColor White
Write-Host ""
Write-Host "Bước tiếp theo:" -ForegroundColor Green
Write-Host "  1. Start API: .\launchers\start_api.ps1" -ForegroundColor White
Write-Host "  2. Test queries qua API hoặc Streamlit UI" -ForegroundColor White
Write-Host ""
Write-Host "Nếu có lỗi, xem:" -ForegroundColor Yellow
Write-Host "  - logs trong artifacts/ingestion_production/logs/" -ForegroundColor White
Write-Host "  - KE_HOACH_RE_INGESTION_INDEXING.md (mục 6: Xử lý lỗi)" -ForegroundColor White
Write-Host ""
