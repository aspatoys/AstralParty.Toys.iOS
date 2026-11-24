<#
.SYNOPSIS
  构建前端（webui/dist）并启动 AstralParty.Toys.iOS 图形界面。

.DESCRIPTION
  `webui/dist/` 是预构建产物，装进仓库就是为了让没装 Node 的机器也能直接跑。
  改了 `webui/src/` 之后用它重建一次再启动，省得记两条命令。

.EXAMPLE
  ./start.ps1
  构建前端后启动界面。

.EXAMPLE
  ./start.ps1 -SkipBuild
  跳过构建，直接用现有的 `webui/dist/` 启动（没装 Node 时用这个）。

.EXAMPLE
  ./start.ps1 -Smoke 6
  起来 6 秒后自动关窗（冒烟用，等价于给 gui.py 传 `--smoke=6`）。
#>
[CmdletBinding()]
param(
    # 跳过 pnpm build，直接用现有的 webui/dist
    [switch]$SkipBuild,
    # 跳过 pnpm install（node_modules 已经是好的）
    [switch]$SkipInstall,
    # 大于 0 时窗口自动关闭，秒数
    [double]$Smoke = 0,
    # 其余参数原样透传给 gui.py
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
$webui = Join-Path $here 'webui'

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

if (-not (Test-Command 'uv')) {
    throw '找不到 uv。装一个：https://docs.astral.sh/uv/'
}

if (-not (Test-Path (Join-Path $here 'gui.py'))) {
    throw "这个脚本要和 gui.py 放在一起（当前目录：$here）"
}

if (-not $SkipBuild) {
    if (-not (Test-Command 'node') -or -not (Test-Command 'pnpm')) {
        throw '构建前端需要 node + pnpm。只想启动的话用 -SkipBuild（需要 webui/dist 已存在）。'
    }

    if (-not (Test-Path (Join-Path $webui 'node_modules')) -and -not $SkipInstall) {
        Write-Host '[start] pnpm install ...' -ForegroundColor Cyan
        Push-Location $webui
        try { pnpm install } finally { Pop-Location }
        if ($LASTEXITCODE -ne 0) { throw 'pnpm install 失败' }
    }

    Write-Host '[start] pnpm build ...' -ForegroundColor Cyan
    Push-Location $webui
    try { pnpm build } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'pnpm build 失败，界面没有启动（避免用旧的 dist 误判）' }
}

if (-not (Test-Path (Join-Path $webui 'dist\index.html'))) {
    throw '找不到 webui/dist/index.html，先不带 -SkipBuild 跑一次'
}

Write-Host '[start] uv run gui.py ...' -ForegroundColor Cyan
$forward = @()
if ($Smoke -gt 0) { $forward += "--smoke=$Smoke" }
if ($AppArgs) { $forward += $AppArgs }
Push-Location $here
try {
    & uv run gui.py @forward
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}

exit $code
