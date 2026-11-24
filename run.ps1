param(
    [Parameter(Position=0, Mandatory=$true)]
    [ValidateSet('check','plan','benchmark','report','year')]
    [string]$Action,
    [int]$Year = 2024,
    [string]$DataRoot,
    [ValidateSet(0,1,2,4,8)]
    [int]$Batch = 0,
    [string]$Python,
    [ValidateSet('hydrodynamics','hydrology','weather','energy','shipping','all')]
    [string]$Group = 'hydrodynamics'
)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $existing = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $Python = if (Test-Path -LiteralPath $existing) { $existing } else { 'python' }
}
$arguments = @((Join-Path $PSScriptRoot 'download.py'), $Action, '--year', $Year, '--group', $Group)
if ($DataRoot) { $arguments += @('--root', $DataRoot) }
if ($Batch) { $arguments += @('--batch', $Batch) }
& $Python @arguments
exit $LASTEXITCODE
