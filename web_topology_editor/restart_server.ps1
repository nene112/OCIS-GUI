param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 8510,
  [int]$WaitSeconds = 12,
  [string]$EdgesPath = ''
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

function Stop-OldServer {
  $procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python(\.exe)?$' -and $_.CommandLine -match 'web_topology_editor.py'
  }
  foreach($proc in $procs){
    try { Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop } catch {}
  }
  Start-Sleep -Milliseconds 400
}

function Resolve-EdgesPath {
  param([string]$RequestedPath)

  $repoRoot = Split-Path -Parent $scriptDir
  $candidates = New-Object System.Collections.Generic.List[string]

  if(-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
    if([System.IO.Path]::IsPathRooted($RequestedPath)) {
      [void]$candidates.Add($RequestedPath)
    } else {
      [void]$candidates.Add((Join-Path $scriptDir $RequestedPath))
      [void]$candidates.Add((Join-Path $repoRoot $RequestedPath))
    }
  }

  [void]$candidates.Add((Join-Path $scriptDir 'mesh\edges.csv'))
  [void]$candidates.Add((Join-Path $scriptDir 'mesh\edges_new.csv'))
  [void]$candidates.Add((Join-Path $repoRoot 'data\ph\mesh\edges.csv'))
  [void]$candidates.Add((Join-Path $repoRoot 'data\ph\mesh\edges_new.csv'))
  [void]$candidates.Add((Join-Path $repoRoot 'data\sj_zonggan-d0\mesh\edges.csv'))
  [void]$candidates.Add((Join-Path $repoRoot 'data\sj_zonggan-d0\mesh\edges_new.csv'))

  foreach($candidate in $candidates) {
    if(Test-Path $candidate) {
      return (Resolve-Path $candidate).Path
    }
  }

  throw "未找到 edges 文件。可通过 -EdgesPath 显式指定，例如: ..\\data\\ph\\mesh\\edges.csv"
}

function Wait-ServerReady {
  param([string]$Url, [int]$TimeoutSec)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while((Get-Date) -lt $deadline){
    try{
      $resp = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 2
      if($resp.StatusCode -eq 200){
        return $resp
      }
    } catch {}
    Start-Sleep -Milliseconds 300
  }
  return $null
}

Stop-OldServer

$resolvedEdgesPath = Resolve-EdgesPath -RequestedPath $EdgesPath

$outLog = Join-Path $scriptDir 'server.stdout.log'
$errLog = Join-Path $scriptDir 'server.stderr.log'
if(Test-Path $outLog){ Remove-Item $outLog -Force -ErrorAction SilentlyContinue }
if(Test-Path $errLog){ Remove-Item $errLog -Force -ErrorAction SilentlyContinue }

$argString = "web_topology_editor.py --host $BindHost --port $Port --edges `"$resolvedEdgesPath`""
$proc = Start-Process -FilePath python -ArgumentList $argString -PassThru -WorkingDirectory $scriptDir -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$url = "http://$BindHost`:$Port/classic"
$ready = Wait-ServerReady -Url $url -TimeoutSec $WaitSeconds
if($null -ne $ready){
  Write-Output "OK: service is up -> $url"
  Write-Output "PID: $($proc.Id)"
  Write-Output "edges: $resolvedEdgesPath"
  exit 0
}

try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch {}
Write-Output "ERROR: service failed to start -> $url"
if(Test-Path $outLog){
  Write-Output '--- stdout ---'
  Get-Content $outLog -Tail 80
}
if(Test-Path $errLog){
  Write-Output '--- stderr ---'
  Get-Content $errLog -Tail 80
}
exit 1
