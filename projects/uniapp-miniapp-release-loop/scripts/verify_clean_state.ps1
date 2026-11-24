# verify_clean_state.ps1 · step7.5 重置后只读回归（不写库、不建预约）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\verify_clean_state.ps1
# 断言：health UP / demo 可登录 / 套餐 4 条且中文正确 / 详情中文可读 / 我的列表 0 条
[CmdletBinding()]
param([string]$BaseUrl = 'http://127.0.0.1:8092')

$ErrorActionPreference = 'Stop'
$script:fails = @()
$tmp = Join-Path $env:TEMP ('ub-clean-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$utf8 = New-Object Text.UTF8Encoding($false)

function Write-Body([string]$name, [string]$json) {
    $p = Join-Path $tmp "$name.json"
    [IO.File]::WriteAllText($p, $json, $utf8)
    return $p
}

function Call-Api {
    param([string]$name, [string]$method, [string]$path, [string]$bodyFile, [string]$token, [int]$expect = 200)
    $out = Join-Path $tmp ([guid]::NewGuid().ToString('N') + '.out')
    $argv = @('-s', '-o', $out, '-w', '%{http_code}', '-X', $method)
    if ($bodyFile) { $argv += @('-H', 'Content-Type: application/json; charset=utf-8', '--data-binary', "@$bodyFile") }
    if ($token) { $argv += @('-H', "Authorization: Bearer $token") }
    $argv += ($BaseUrl + $path)
    $code = (& curl.exe @argv).Trim()
    $resp = if (Test-Path $out) { [IO.File]::ReadAllText($out, $utf8) } else { '' }
    if ($code -ne "$expect") {
        $script:fails += "$name HTTP=$code expect=$expect"
        Write-Host "FAIL $name HTTP=$code body=$resp"
    } else {
        Write-Host "PASS $name HTTP=$code"
    }
    return $resp
}

function Check([bool]$cond, [string]$msg) {
    if ($cond) { Write-Host "PASS $msg" } else { $script:fails += $msg; Write-Host "FAIL $msg" }
}

$r = [ordered]@{ time = (Get-Date).ToString('s'); baseUrl = $BaseUrl; checks = @() }

Write-Host "=== 重置后只读回归 $BaseUrl ==="
$health = (Call-Api 'GET /actuator/health' 'GET' '/actuator/health') | ConvertFrom-Json
Check ($health.status -eq 'UP') 'health=UP'
$r.health = $health.status

$login = (Call-Api 'POST /api/auth/login' 'POST' '/api/auth/login' (Write-Body 'login' '{"account":"demo","password":"welcome1"}')) | ConvertFrom-Json
Check ($login.code -eq 0) 'demo 登录 code=0'
Check ([bool]$login.data.token) '登录返回 token'
$token = $login.data.token

$pkgs = (Call-Api 'GET /api/packages' 'GET' '/api/packages?page=1&size=10' $null $token) | ConvertFrom-Json
Check ($pkgs.code -eq 0) '套餐列表 code=0'
Check ($pkgs.data.total -eq 4) ('套餐 total=4（实测 ' + $pkgs.data.total + '）')
$titles = @($pkgs.data.list | ForEach-Object { $_.title })
Check (($titles -join '|') -eq '城市轻写真|复古胶片|情侣纪实|个人写真·夜场') ('套餐中文标题顺序正确（' + ($titles -join '|') + '）')
$r.packages = $pkgs.data

$detail = (Call-Api 'GET /api/packages/1' 'GET' '/api/packages/1' $null $token) | ConvertFrom-Json
Check ($detail.code -eq 0) '套餐详情 code=0'
Check ($detail.data.title -eq '城市轻写真') '详情标题=城市轻写真'
Check ($detail.data.summary -like '*室内自然光棚拍*') '详情说明中文可读'
$r.packageDetail = $detail.data

$mine = (Call-Api 'GET /api/bookings' 'GET' '/api/bookings?page=1&size=10' $null $token) | ConvertFrom-Json
Check ($mine.code -eq 0) '我的列表 code=0'
Check ($mine.data.total -eq 0) ('我的列表 total=0（实测 ' + $mine.data.total + '）')
$r.bookings = $mine.data

$outDir = Join-Path $PSScriptRoot '..\07_联调\evidence'
$outDir = [IO.Path]::GetFullPath($outDir)
$r.fails = $script:fails
$r.pass = ($script:fails.Count -eq 0)
[IO.File]::WriteAllText((Join-Path $outDir 'step7_5_api_after_reset.json'), ($r | ConvertTo-Json -Depth 8), $utf8)

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

if ($script:fails.Count -gt 0) {
    Write-Host ('=== 失败 ' + $script:fails.Count + ' 项：' + ($script:fails -join '；'))
    exit 1
}
Write-Host '=== 重置后只读回归全部通过 ==='
exit 0
