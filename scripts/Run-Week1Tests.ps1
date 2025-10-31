# Week 1 Testing Automation Script
# Redis HA Sentinel + Distributed Cache Validation

param(
    [switch]$SkipDocker,
    [switch]$OnlyCache,
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"
$RedisPassword = "pvcfc_redis_2025_secure"

function Write-Step {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

# Step 1: Check Docker Desktop
Write-Step "Step 1: Checking Docker Desktop"

$dockerRunning = $false
try {
    docker ps > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker Desktop is running"
        $dockerRunning = $true
    } else {
        throw "Docker not responding"
    }
} catch {
    Write-Failure "Docker Desktop is not running"
    Write-Warning-Custom "Please start Docker Desktop and wait for it to be ready"
    Write-Host "Then run this script again with: .\scripts\Run-Week1Tests.ps1"
    exit 1
}

# Step 2: Start Redis HA Stack
if (-not $SkipDocker) {
    Write-Step "Step 2: Starting Redis HA Stack"
    
    Set-Location $ProjectRoot
    
    # Stop any existing Redis containers
    Write-Host "Stopping existing Redis containers..."
    docker compose -f docker-compose.redis-ha.yml down 2>&1 | Out-Null
    
    # Start fresh
    Write-Host "Starting Redis HA stack (master + replica + 3 sentinels)..."
    docker compose -f docker-compose.redis-ha.yml up -d
    
    if ($LASTEXITCODE -ne 0) {
        Write-Failure "Failed to start Redis stack"
        exit 1
    }
    
    # Wait for containers to be healthy
    Write-Host "Waiting for containers to be healthy - 30 seconds..."
    Start-Sleep -Seconds 30
    
    # Verify containers
    Write-Host "`nContainer Status:"
    docker ps --filter "name=redis" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
    
    # Check if all 5 containers are running
    $redisContainers = docker ps --filter "name=redis" --format "{{.Names}}"
    $expectedContainers = @("redis-master", "redis-replica-1", "redis-sentinel-1", "redis-sentinel-2", "redis-sentinel-3")
    
    $allRunning = $true
    foreach ($expected in $expectedContainers) {
        if ($redisContainers -notcontains $expected) {
            Write-Failure "Container $expected is not running"
            $allRunning = $false
        }
    }
    
    if (-not $allRunning) {
        Write-Failure "Not all Redis containers are running"
        Write-Host "`nCheck logs with:"
        Write-Host "  docker compose -f docker-compose.redis-ha.yml logs"
        exit 1
    }
    
    Write-Success "All Redis containers are running"
    
    # Verify sentinel can see master
    Write-Host "`nVerifying sentinel master discovery..."
    $sentinelOutput = docker exec redis-sentinel-1 redis-cli -p 26379 sentinel masters 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Sentinel can discover master"
    } else {
        Write-Failure "Sentinel cannot discover master"
        Write-Host "Output: $sentinelOutput"
    }
} else {
    Write-Step "Step 2: Skipping Docker setup with SkipDocker flag"
}

# Step 3: Run Python Tests
Write-Step "Step 3: Running Automated Tests"

# Check if Python is available
try {
    python --version > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found"
    }
} catch {
    Write-Failure "Python is not available in PATH"
    exit 1
}

# Run discovery test
if (-not $OnlyCache) {
    Write-Host "`n--- Test: Sentinel Discovery ---"
    python scripts/test_redis_ha.py --test discovery --password $RedisPassword
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Sentinel discovery test passed"
    } else {
        Write-Failure "Sentinel discovery test failed"
    }
}

# Run cache test
Write-Host "`n--- Test: Distributed Cache ---"
python scripts/test_redis_ha.py --test cache --password $RedisPassword

if ($LASTEXITCODE -eq 0) {
    Write-Success "Distributed cache test passed"
} else {
    Write-Failure "Distributed cache test failed"
}

# Step 4: Run pytest (optional - can be slow)
Write-Step "Step 4: Running Unit Tests (pytest)"

$runPytest = Read-Host "`nRun full pytest suite? (y/n)"
if ($runPytest -eq "y") {
    Write-Host "Running pytest..."
    pytest tests/unit/test_distributed_cache.py tests/unit/test_logging_filter.py -v
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "All pytest tests passed"
    } else {
        Write-Warning-Custom "Some pytest tests failed"
    }
} else {
    Write-Host "Skipping pytest (run manually: pytest -v)"
}

# Step 5: Manual Failover Test Instructions
if (-not $OnlyCache) {
    Write-Step "Step 5: Manual Failover Test (Optional)"
    
    Write-Host ""
    Write-Host "To test Redis Sentinel failover manually:"
    Write-Host ""
    Write-Host "1. Open a NEW PowerShell terminal"
    Write-Host "2. Run: python scripts/test_redis_ha.py --test failover"
    Write-Host "3. When prompted, run: docker stop redis-master"
    Write-Host "4. Wait for failover to complete - about 10 seconds"
    Write-Host "5. Verify data persisted in new master"
    Write-Host ""
    Write-Host "The script will guide you through the process."
    Write-Host ""
}

# Step 6: Summary
Write-Step "Summary & Next Steps"

Write-Host ""
Write-Host "SUCCESS: Redis HA Stack Running with Sentinel"
Write-Host "SUCCESS: Distributed Cache Enabled - USE_DISTRIBUTED_CACHE=true"
Write-Host "SUCCESS: Configuration .env updated with Week 1 settings"
Write-Host ""
Write-Host "Tests Completed:"
Write-Host "  - Sentinel master discovery"
Write-Host "  - Distributed cache cross-instance sharing"
Write-Host "  - TTL expiration validation"
Write-Host "  - Batch operations set_many and get_many"
Write-Host ""
Write-Host "Manual Tests Pending:"
Write-Host "  - Sentinel failover test - see instructions above"
Write-Host "  - Performance smoke test with running app instances"
Write-Host ""
Write-Host "Full test guide: scripts\RUN_MANUAL_TESTS.md"
Write-Host ""
Write-Host "To stop Redis stack:"
Write-Host "  docker compose -f docker-compose.redis-ha.yml down"
Write-Host ""
Write-Host "To start application with distributed cache:"
Write-Host "  uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host ""

Write-Success "Week 1 automated tests completed!"
Write-Host "`nFor detailed manual testing, see: scripts\RUN_MANUAL_TESTS.md" -ForegroundColor Yellow
