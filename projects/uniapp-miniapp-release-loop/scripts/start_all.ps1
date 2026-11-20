# start_all.ps1 · T-701 一键启动（依赖容器 → 后端 8092 → 云函数 8093 → 探针 → 可选冒烟）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 [-Rebuild] [-Smoke]
# 说明：三件 = MySQL/Redis/RabbitMQ（Docker）+ booking-service(8092) + 云函数 apiProxy(8093)
#       H5 5186 属 5B，尚未落地；脚本检测到 frontend/package.json 才会提示，不假装已启动。
#       APP_SECRET 从 05_代码/cloud-functions/.env 读取（与后端共用同一值）；无 .env 时两端都用 dev 默认值。
[CmdletBinding()]
param([switch]$Rebuild, [switch]$Smoke)

$ErrorActionPreference = 'Stop'
$proj = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $proj '05_代码\backend\booking-service'
$jar = Join-Path $backend 'target\booking-service.jar'
$ev = Join-Path $proj '05_代码\backend\evidence'
$cf = Join-Path $proj '05_代码\cloud-functions'
$cfEv = Join-Path $cf 'evidence'
$java = 'D:\java\jdk-17\bin\java.exe'
if (-not (Test-Path $java)) { $java = 'java' }

function Test-Port([int]$port) {
    return @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue).Count -gt 0
}

function Import-DotEnv([string]$path) {
    # 只解析 KEY=VALUE，忽略注释/空行/空值；写进当前进程环境，子进程继承
    Get-Content -LiteralPath $path -Encoding utf8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) { return }
        $i = $line.IndexOf('=')
        if ($i -le 0) { return }
        $k = $line.Substring(0, $i).Trim()
        $v = $line.Substring($i + 1).Trim().Trim('"')
        if ($v -ne '') { [Environment]::SetEnvironmentVariable($k, $v, 'Process') }
    }
}

if (-not (Test-Path $cfEv)) { New-Item -ItemType Directory -Force $cfEv | Out-Null }

Write-Host '[0/5] 加载云函数环境变量'
$envFile = Join-Path $cf '.env'
if (Test-Path $envFile) {
    Import-DotEnv $envFile
    Write-Host "  已加载 $envFile"
} else { Write-Host '  未发现 .env（两端使用 dev 默认 APP_SECRET；生产必须配置）' }
if (-not $env:CF_BACKEND_BASE) { $env:CF_BACKEND_BASE = 'http://127.0.0.1:8092' }
if (-not $env:CF_PORT) { $env:CF_PORT = '8093' }

Write-Host '[1/5] 依赖容器（rag-mysql / rag-redis / rag-rabbitmq）'
foreach ($c in @('rag-mysql', 'rag-redis', 'rag-rabbitmq')) {
    $running = (& docker inspect -f '{{.State.Running}}' $c 2>$null)
    if ($running -ne 'true') { & docker start $c | Out-Null; Write-Host "  启动容器 $c" }
    else { Write-Host "  已在运行 $c" }
}
foreach ($p in @(3308, 6379, 5672)) {
    $ok = $false
    for ($i = 0; $i -lt 30; $i++) { if (Test-Port $p) { $ok = $true; break }; Start-Sleep -Seconds 1 }
    if (-not $ok) { Write-Host "  ❌ 端口 $p 未就绪"; exit 1 }
}
Write-Host '  端口 3308/6379/5672 就绪'

Write-Host '[2/5] 后端构建'
if ((-not (Test-Path $jar)) -or $Rebuild) {
    Push-Location $backend
    & mvn -q -DskipTests package
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Write-Host '  ❌ mvn package 失败'; exit 1 }
    Write-Host '  构建完成'
} else { Write-Host '  使用已有 jar（-Rebuild 强制重建）' }

Write-Host '[3/5] 启动 booking-service (8092)'
if (Test-Port 8092) {
    Write-Host '  8092 已在监听，跳过启动（若刚改过 APP_SECRET 需先 stop_all 再启动）'
} else {
    $proc = Start-Process -FilePath $java -ArgumentList '-Dfile.encoding=UTF-8', '-Xmx512m', '-jar', $jar `
        -RedirectStandardOutput (Join-Path $ev 'app_run.log') `
        -RedirectStandardError (Join-Path $ev 'app_run.err.log') -WindowStyle Hidden -PassThru
    Write-Host "  PID=$($proc.Id)"
}
$up = $false
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8092/actuator/health' -TimeoutSec 3; if ($h.status -eq 'UP') { $up = $true; break } } catch {}
}
if (-not $up) { Write-Host '  ❌ health 未 UP（查看 evidence/app_run.err.log）'; exit 1 }
Write-Host '  ✅ /actuator/health = UP'

Write-Host '[4/5] 启动云函数 apiProxy (8093)'
if (Test-Port 8093) {
    Write-Host '  8093 已在监听，跳过启动'
} else {
    $entry = Join-Path $cf 'apiProxy\localServer.js'
    if (-not (Test-Path $entry)) { Write-Host "  ❌ 未找到 $entry"; exit 1 }
    $node = (Get-Command node -ErrorAction SilentlyContinue)
    if (-not $node) { Write-Host '  ❌ 未找到 node（需 Node 18+）'; exit 1 }
    $cfProc = Start-Process -FilePath 'node' -ArgumentList '--max-old-space-size=256', 'apiProxy/localServer.js' `
        -WorkingDirectory $cf `
        -RedirectStandardOutput (Join-Path $cfEv 'cf_8093.log') `
        -RedirectStandardError (Join-Path $cfEv 'cf_8093.err.log') -WindowStyle Hidden -PassThru
    Write-Host "  PID=$($cfProc.Id)"
}
$cfUp = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try { $hz = Invoke-RestMethod -Uri 'http://127.0.0.1:8093/healthz?probe=1' -TimeoutSec 5; $cfUp = $true; break } catch {}
}
if (-not $cfUp) { Write-Host '  ❌ 云函数 8093 未就绪（查看 evidence/cf_8093.err.log）'; exit 1 }
if ($hz.backendProbe.code -ne 0) {
    Write-Host "  ❌ 云函数→后端探针失败：code=$($hz.backendProbe.code) msg=$($hz.backendProbe.msg)"
    Write-Host '     多为 APP_SECRET 不一致：stop_all 后重跑本脚本（两端会读同一个 .env）'
    exit 1
}
Write-Host "  ✅ /healthz = UP；探针 code=0 elapsedMs=$($hz.backendProbe.elapsedMs)"

Write-Host '[5/5] 冒烟'
if (Test-Path (Join-Path $proj '05_代码\frontend\package.json')) {
    Write-Host '  H5 dev 需另起（5B 已落地时手动 npm run dev:h5）'
} else { Write-Host '  H5 5186 尚未落地（5B 未开始），跳过' }
if ($Smoke) {
    & (Join-Path $PSScriptRoot 'smoke.ps1')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host '  未指定 -Smoke，跳过 curl 集（可随时单独跑 scripts\smoke.ps1）'
}
Write-Host '启动完成（依赖容器 + 后端 8092 + 云函数 8093）。'
