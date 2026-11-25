# restart_walk_env.ps1 · 第 9 步走查现场一键重起（幂等：已在线则跳过）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\restart_walk_env.ps1 [-NoProbe]
# 做了什么：后端 8092（MYSQL_PORT=3307）→ 云函数 8093 → H5 dev 5186 → 库计数 → 只读渲染探针
# 不做什么：不碰 MySQL/Redis（本机原生，已常驻）；不重启 Docker、不伪造 MQ
[CmdletBinding()]
param([switch]$NoProbe)

$ErrorActionPreference = 'Stop'
$proj = Split-Path $PSScriptRoot -Parent
$ev = Join-Path $proj '05_代码\backend\evidence'
$cfEv = Join-Path $proj '05_代码\cloud-functions\evidence'
$fe = Join-Path $proj '05_代码\frontend'
$stamp = Get-Date -Format 'yyyyMMdd'
$java = 'D:\java\jdk-17\bin\java.exe'
if (-not (Test-Path $java)) { $java = 'java' }

function Test-Port([int]$p) { return @(Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue).Count -gt 0 }
function Wait-Http([string]$url, [int]$tries = 60, [int]$sleepSec = 2) {
    for ($i = 0; $i -lt $tries; $i++) {
        try { $r = Invoke-WebRequest $url -TimeoutSec 5 -UseBasicParsing; if ($r.StatusCode -eq 200) { return $true } } catch {}
        Start-Sleep -Seconds $sleepSec
    }
    return $false
}

# 1) 后端 8092
if (Test-Port 8092) { Write-Host '[1/4] 8092 已在线，跳过' }
else {
    $env:MYSQL_PORT = '3307'; $env:MYSQL_HOST = '127.0.0.1'; $env:REDIS_PORT = '6379'
    if (-not (Test-Path $ev)) { New-Item -ItemType Directory -Force $ev | Out-Null }
    $p = Start-Process -FilePath $java -ArgumentList '-Dfile.encoding=UTF-8', '-Xmx512m', '-jar', 'booking-service.jar' `
        -WorkingDirectory (Join-Path $proj '05_代码\backend\booking-service\target') `
        -RedirectStandardOutput (Join-Path $ev "app_run_$stamp.log") `
        -RedirectStandardError (Join-Path $ev "app_run_$stamp.err.log") -WindowStyle Hidden -PassThru
    Write-Host "[1/4] 后端启动 PID=$($p.Id)，等待 /api/packages ..."
    if (-not (Wait-Http 'http://127.0.0.1:8092/api/packages' 60 2)) { Write-Host '  ❌ 后端 120s 未就绪，看 evidence/app_run_*.err.log'; exit 1 }
}

# 2) 云函数 8093
if (Test-Port 8093) { Write-Host '[2/4] 8093 已在线，跳过' }
else {
    if (-not (Test-Path $cfEv)) { New-Item -ItemType Directory -Force $cfEv | Out-Null }
    $env:CF_BACKEND_BASE = 'http://127.0.0.1:8092'; $env:CF_PORT = '8093'
    $p = Start-Process -FilePath 'node' -ArgumentList '--max-old-space-size=256', 'apiProxy/localServer.js' `
        -WorkingDirectory (Join-Path $proj '05_代码\cloud-functions') `
        -RedirectStandardOutput (Join-Path $cfEv "cf_8093_$stamp.log") `
        -RedirectStandardError (Join-Path $cfEv "cf_8093_$stamp.err.log") -WindowStyle Hidden -PassThru
    Write-Host "[2/4] 云函数启动 PID=$($p.Id)"
    if (-not (Wait-Http 'http://127.0.0.1:8093/healthz?probe=1' 20 1)) { Write-Host '  ❌ 8093 未就绪'; exit 1 }
}

# 3) H5 5186
if (Test-Port 5186) { Write-Host '[3/4] 5186 已在线，跳过' }
else {
    $p = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev:h5' -WorkingDirectory $fe `
        -RedirectStandardOutput (Join-Path $fe "evidence_h5_$stamp.log") `
        -RedirectStandardError (Join-Path $fe "evidence_h5_$stamp.err.log") -WindowStyle Hidden -PassThru
    Write-Host "[3/4] H5 dev 启动 PID=$($p.Id)（首次编译约 60–90s）"
    if (-not (Wait-Http 'http://127.0.0.1:5186/' 80 2)) { Write-Host '  ❌ 5186 未就绪，看 frontend/evidence_h5_*.log'; exit 1 }
}

# 4) 现场快照
Write-Host '[4/4] 现场状态'
foreach ($pt in 5186, 8092, 8093, 3307, 6379, 5672) {
    $c = @(Get-NetTCPConnection -State Listen -LocalPort $pt -ErrorAction SilentlyContinue)
    if ($c.Count) { Write-Host ("  {0} LISTEN pid={1}" -f $pt, $c[0].OwningProcess) } else { Write-Host "  $pt DOWN" }
}
$counts = py -3.11 -c "import pymysql;c=pymysql.connect(host='127.0.0.1',port=3307,user='root',password='123456',database='uniapp_booking');cur=c.cursor();cur.execute('select (select count(*) from user),(select count(*) from package),(select count(*) from booking),(select count(*) from notify_log),(select max(id) from booking)');print(cur.fetchone());c.close()"
Write-Host "  DB user/package/booking/notify_log/max_id = $counts"
Write-Host '  打开 http://127.0.0.1:5186/ （手机宽度与桌面宽度各走一遍）'

if (-not $NoProbe) {
    Write-Host '只读渲染探针 ...'
    Push-Location $proj
    node (Join-Path $PSScriptRoot '..\09_验收\scripts\render_probe_readonly.cjs') $stamp
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Write-Host '  ❌ 探针有 FAIL，见 09_验收/evidence/step9_render_probe_*.json'; exit $code }
}

Write-Host '现场就绪。'
