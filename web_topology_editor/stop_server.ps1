$ErrorActionPreference = 'Stop'
$procs = Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match '^python(\.exe)?$' -and $_.CommandLine -match 'web_topology_editor.py'
}
foreach($proc in $procs){
  try { Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop } catch {}
}
Start-Sleep -Milliseconds 300
Write-Output ('stopped=' + (@($procs).Count))
