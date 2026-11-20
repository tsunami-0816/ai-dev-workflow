# stop_all.ps1 · T-701 停止本项目进程（云函数 8093 + 后端 8092），不碰共享 MySQL/Redis/RabbitMQ 容器
# 用法：powershell -ExecutionPolicy Bypass -File scripts\stop_all.ps1
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Test-Port([int]$port) {
    return @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue).Count -gt 0
}

Write-Host '[1/3] 停止云函数 apiProxy（8093）'
$cfPids = @(Get-NetTCPConnection -State Listen -LocalPort 8093 -ErrorAction SilentlyContinue).OwningProcess
$cfFound = $false
foreach ($id in $cfPids) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if ($p -and $p.Name -eq 'node.exe' -and $p.CommandLine -like '*localServer.js*') {
        Write-Host "  停止 node PID=$id（$($p.CommandLine))"
        Stop-Process -Id $id -Force
        $cfFound = $true
    } elseif ($p) {
        Write-Host "  ⚠️ 8093 被非本项目进程占用（PID=$id $($p.Name)），不动它"
        exit 1
    }
}
if (-not $cfFound) { Write-Host '  未发现运行中的 apiProxy（8093 空闲）' }

Write-Host '[2/3] 查找本项目 java 进程（CommandLine 含 booking-service.jar）'
$procs = Get-CimInstance Win32_Process -Filter "Name='java.exe'" |
    Where-Object { $_.CommandLine -like '*booking-service.jar*' }
if (-not $procs) { Write-Host '  未发现运行中的 booking-service' }
foreach ($p in $procs) {
    Write-Host "  停止 PID=$($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force
}

Write-Host '[3/3] 验证端口释放'
foreach ($port in @(8093, 8092)) {
    $ok = $false
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Test-Port $port)) { $ok = $true; break }
        Start-Sleep -Seconds 1
    }
    if ($ok) { Write-Host "  ✅ $port 已释放" } else { Write-Host "  ❌ $port 仍被占用，请检查"; exit 1 }
}
Write-Host '  共享依赖容器保留运行（MySQL 3308 / Redis 6379 / RabbitMQ 5672）'
Write-Host '停止完成。'
