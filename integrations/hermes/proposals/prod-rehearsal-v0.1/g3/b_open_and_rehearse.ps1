# G3-B. OPENS REAL DATA. Needs the owner's signed G3-DECISIONS.md. Refuses unless G3-A passed and its protections still hold.
# Makes one disk from the rehearsal snapshot, attaches it read-only to the isolated VM, and runs the rehearsal once. Never boots from it.
param([Parameter(Mandatory = $true)][string]$ConfirmOpen)
. "$PSScriptRoot\common.ps1"
$Dir = Join-Path $Here 'b'
New-Item -ItemType Directory -Force $Dir | Out-Null
function Done([string]$r, [int]$rc) { Write-Output "G3B $r"; [IO.File]::WriteAllText("$Dir\RESULT.txt", "$r`n"); exit $rc }
if ($ConfirmOpen -ne 'OPEN-REAL-DATA-G3') { Done 'REFUSED confirmation' 3 }
if (Test-Path "$Dir\started") { Write-Output 'G3B STOPPED already started'; exit 2 }   # never overwrites the first run's result
if (-not (Test-Path (Join-Path $Here 'a\RESULT.txt')) -or ((Get-Content (Join-Path $Here 'a\RESULT.txt') -Raw).Trim() -ne 'PASS')) { Done 'STOPPED G3-A has not passed' 2 }
if (-not (Test-Path (Join-Path $Here 'DECISIONS-SIGNED.txt'))) { Done 'STOPPED decisions not signed' 2 }
if (@(Get-DeployerBindings | Where-Object { $Roles -contains $_.role }).Count) { Done 'STOPPED deployer binding is back' 2 }
$r = Invoke-G @('compute', 'snapshots', 'describe', $Snapshot, "--project=$Project", '--format=json') "$Dir\snapshot.json"
if ($r.Code -ne 0) { Done 'STOPPED snapshot describe' 2 }
$s = $r.Text | ConvertFrom-Json
if ([string]$s.id -ne $SnapshotId -or $s.status -ne 'READY') { Done 'STOPPED snapshot differs' 2 }
$r = Invoke-G @('compute', 'instances', 'describe', $Vm, "--zone=$Zone", "--project=$Project", '--format=json') "$Dir\vm.json"
if ($r.Code -ne 0) { Done 'STOPPED vm describe' 2 }
$i = $r.Text | ConvertFrom-Json
if (@($i.serviceAccounts | Where-Object { $_ }).Count -or @($i.networkInterfaces)[0].accessConfigs -or ((@($i.networkInterfaces)[0].network -split '/')[-1]) -ne 'lilith-rehearsal') { Done 'STOPPED vm isolation changed' 2 }
New-Item -ItemType File "$Dir\started" | Out-Null
$r = Invoke-G @('compute', 'disks', 'create', $Copy, "--source-snapshot=$Snapshot", '--type=pd-balanced', "--zone=$Zone", "--project=$Project", '--labels=app=lilith,purpose=rehearsal,go=g3-20261101') "$Dir\disk.txt"
if ($r.Code -ne 0) { Done "STOPPED disk create rc $($r.Code)" 2 }
$r = Invoke-G @('compute', 'instances', 'attach-disk', $Vm, "--disk=$Copy", '--device-name=copy', '--mode=ro', "--zone=$Zone", "--project=$Project") "$Dir\attach.txt"
if ($r.Code -ne 0) { Done "STOPPED attach rc $($r.Code)" 2 }
$r = Invoke-Guest 'guest_rehearsal.sh' 'REAL' "$Dir\rehearsal.txt"
if ($r.Text -notmatch '(?m)^REHEARSAL PASS') { Done 'STOPPED rehearsal did not pass' 2 }
Done 'PASS' 0
