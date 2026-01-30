# ============================================
# Production-Grade Port Reservation for Docker
# ============================================
# This script permanently reserves your application ports
# so Windows Hyper-V won't randomly assign them.
#
# Run as Administrator: Right-click → Run as Administrator
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Docker Port Reservation Fix" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click this script and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "Admin privileges confirmed ✓" -ForegroundColor Green
Write-Host ""

# Define your application ports (from docker-compose.yml)
# Using ports that avoid Windows Hyper-V dynamic range conflicts
$ports = @(
    3000,  # Frontend (React standard port)
    5432,  # PostgreSQL (standard port)
    5555,  # Flower (Celery monitoring - standard port)
    7379,  # Redis (high port 7xxx - safe from Windows conflicts)
    8080   # Backend API (common Python/FastAPI port)
)

Write-Host "Reserving application ports to prevent Hyper-V conflicts..." -ForegroundColor Yellow
Write-Host ""

foreach ($port in $ports) {
    Write-Host "Reserving port $port..." -ForegroundColor Cyan

    # Check if already reserved
    $existing = netsh interface ipv4 show excludedportrange protocol=tcp | Select-String "^\s+$port\s+"

    if ($existing) {
        Write-Host "  ℹ️  Port $port is already in an excluded range" -ForegroundColor Gray
    } else {
        # Reserve the port
        $result = netsh int ipv4 add excludedportrange protocol=tcp startport=$port numberofports=1 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Port $port reserved successfully!" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  Could not reserve port $port (may already be in use or reserved)" -ForegroundColor Yellow
            Write-Host "     Error: $result" -ForegroundColor Gray
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Current Port Exclusion Ranges:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
netsh interface ipv4 show excludedportrange protocol=tcp | Select-String -Pattern "^\s+\d+\s+" | Select-Object -First 30

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✓ Port Reservation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Restart your computer for changes to take full effect" -ForegroundColor White
Write-Host "2. Run 'docker-compose up -d' to start services" -ForegroundColor White
Write-Host ""
Write-Host "These ports are now permanently reserved and won't" -ForegroundColor White
Write-Host "conflict with Windows Hyper-V after reboot!" -ForegroundColor White
Write-Host ""

pause
