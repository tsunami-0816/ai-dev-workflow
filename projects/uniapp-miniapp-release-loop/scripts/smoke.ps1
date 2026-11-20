# smoke.ps1 · T-701 冒烟 curl 集（6 个操作 + health，全 200 才算过）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1
[CmdletBinding()]
param([string]$BaseUrl = 'http://127.0.0.1:8092')

$ErrorActionPreference = 'Stop'
$script:fails = @()
$tmp = Join-Path $env:TEMP ('ub-smoke-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$script:tmp = $tmp

function Write-Body([string]$name, [string]$json) {
    $p = Join-Path $script:tmp "$name.json"
    [IO.File]::WriteAllText($p, $json, (New-Object Text.UTF8Encoding($false)))
    return $p
}

function Call-Api {
    param([string]$name, [string]$method, [string]$path, [string]$bodyFile, [string]$token, [int]$expect = 200)
    $out = Join-Path $script:tmp ([guid]::NewGuid().ToString('N') + '.out')
    $argv = @('-s', '-o', $out, '-w', '%{http_code}', '-X', $method)
    if ($bodyFile) { $argv += @('-H', 'Content-Type: application/json; charset=utf-8', '--data-binary', "@$bodyFile") }
    if ($token) { $argv += @('-H', "Authorization: Bearer $token") }
    $argv += ($BaseUrl + $path)
    $code = (& curl.exe @argv).Trim()
    $resp = if (Test-Path $out) { Get-Content $out -Raw -Encoding UTF8 } else { '' }
    if ($code -ne "$expect") {
        $script:fails += "$name HTTP=$code expect=$expect"
        Write-Host "FAIL $name HTTP=$code body=$resp"
    } else {
        Write-Host "PASS $name HTTP=$code"
    }
    return $resp
}

Write-Host "=== 冒烟 curl 集 $BaseUrl ==="
$health = Call-Api 'GET /actuator/health' 'GET' '/actuator/health'
if (($health | ConvertFrom-Json).status -ne 'UP') {
    $script:fails += 'health 不是 UP'
    Write-Host 'FAIL health 不是 UP'
}

$loginBody = Write-Body 'login' '{"account":"demo","password":"welcome1"}'
$login = (Call-Api 'POST /api/auth/login' 'POST' '/api/auth/login' $loginBody) | ConvertFrom-Json
if ($login.code -ne 0) { $script:fails += 'login code!=0'; Write-Host 'FAIL login code!=0' }
$token = $login.data.token

Call-Api 'GET /api/packages' 'GET' '/api/packages?page=1&size=4' | Out-Null
Call-Api 'GET /api/packages/2' 'GET' '/api/packages/2' | Out-Null

$date = (Get-Date).AddDays(1).ToString('yyyy-MM-dd')
$bookingBody = Write-Body 'booking' ('{"packageId":1,"bookDate":"' + $date + '","slot":"上午","contact":"13700001234","remark":"smoke 冒烟"}')
$created = (Call-Api 'POST /api/bookings' 'POST' '/api/bookings' $bookingBody $token) | ConvertFrom-Json
if ($created.code -ne 0) { $script:fails += 'booking code!=0'; Write-Host 'FAIL booking code!=0' }

Call-Api 'GET /api/bookings' 'GET' '/api/bookings?page=1&size=5' $null $token | Out-Null
Call-Api 'POST /api/auth/logout' 'POST' '/api/auth/logout' $null $token | Out-Null

# 附加断言：登出后旧 token 必须 40103（不计入“全 200”口径）
$code = (& curl.exe -s -o (Join-Path $tmp 'after.out') -w '%{http_code}' -H "Authorization: Bearer $token" ($BaseUrl + '/api/bookings')).Trim()
if ($code -eq '401') { Write-Host 'PASS 登出后旧 token 被拒 HTTP=401' }
else { $script:fails += "登出后旧 token 未拒绝 HTTP=$code"; Write-Host "FAIL 登出后旧 token HTTP=$code" }

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

if ($script:fails.Count -gt 0) {
    Write-Host ("=== 失败 " + $script:fails.Count + " 项：" + ($script:fails -join '；'))
    exit 1
}
Write-Host '=== 冒烟全部通过 ==='
exit 0
