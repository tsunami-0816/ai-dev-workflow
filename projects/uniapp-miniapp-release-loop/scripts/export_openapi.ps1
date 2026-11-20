# export_openapi.ps1 · T-704 契约导出：/v3/api-docs → 06.5_契约/openapi.json
# 用法：powershell -ExecutionPolicy Bypass -File scripts\export_openapi.ps1
[CmdletBinding()]
param([string]$BaseUrl = 'http://127.0.0.1:8092')

$ErrorActionPreference = 'Stop'
$proj = Split-Path $PSScriptRoot -Parent
$repo = Split-Path (Split-Path $proj -Parent) -Parent
$out = Join-Path $proj '06.5_契约\openapi.json'
$validator = Join-Path $repo 'scripts\api_contract_validator.py'

Write-Host "导出 $BaseUrl/v3/api-docs → $out"
& python $validator export "$BaseUrl/v3/api-docs" $out
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& python (Join-Path $PSScriptRoot 'verify_openapi.py') $out
exit $LASTEXITCODE
