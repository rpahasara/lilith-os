# Last-resort restore of lilith-01 from a snapshot (PREPARED, NOT APPROVED, NOT RUN). Everything written after that snapshot is lost from the running disk, so it is refused once the return window closes.
# The current disk is detached and KEPT. Stops at the first failure, with no retry, and prints where things stand.
param([Parameter(Mandatory = $true)][string]$Confirm, [Parameter(Mandatory = $true)][string]$Snapshot)
. "$PSScriptRoot\common.ps1"
if ($Confirm -ne 'RESTORE-LILITH-01') { Write-Output 'RESTORE REFUSED confirmation'; exit 3 }
$w = Join-Path $Here 'RETURN-WINDOW.txt'
if (-not (Test-Path $w) -or [datetime]::Parse((Get-Content $w -Raw).Trim()).ToUniversalTime() -lt [datetime]::UtcNow) { Write-Output 'RESTORE REFUSED outside the return window: fix forward'; exit 3 }
$r = Invoke-G @('compute', 'snapshots', 'describe', $Snapshot, "--project=$Project", '--format=json')
if ($r.Code -ne 0) { Write-Output 'RESTORE STOPPED snapshot not found'; exit 2 }
$s = $r.Text | ConvertFrom-Json
if ($s.status -ne 'READY' -or ($s.sourceDisk -split '/')[-1] -ne $Disk) { Write-Output 'RESTORE STOPPED snapshot is not a READY snapshot of lilith-01'; exit 2 }
$new = "lilith-01-restored-$((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmm'))"
$t0 = Get-Date
foreach ($c in @(
    @('compute', 'disks', 'create', $new, "--source-snapshot=$Snapshot", '--type=pd-balanced', "--zone=$Zone", "--project=$Project", '--format=none'),
    @('compute', 'instances', 'stop', $Vm, "--zone=$Zone", "--project=$Project", '--format=none'),
    @('compute', 'instances', 'detach-disk', $Vm, "--disk=$Disk", "--zone=$Zone", "--project=$Project", '--format=none'),
    @('compute', 'instances', 'attach-disk', $Vm, "--disk=$new", '--boot', "--zone=$Zone", "--project=$Project", '--format=none'),
    @('compute', 'instances', 'start', $Vm, "--zone=$Zone", "--project=$Project", '--format=none'))) {
    $r = Invoke-G $c
    Write-Output "$($c[1..2] -join ' ') rc $($r.Code)"
    if ($r.Code -ne 0) { Write-Output "RESTORE STOPPED at $($c[2]). Old disk $Disk is kept; new disk $new. Report before anything else."; exit 2 }
}
$r = Invoke-G @('compute', 'disks', 'add-resource-policies', $new, "--zone=$Zone", "--project=$Project", "--resource-policies=$Schedule", '--format=none')
Write-Output "schedule on new disk rc $($r.Code)"
Write-Output "RESTORE BOOTED on $new in $([int]((Get-Date) - $t0).TotalSeconds)s. Old disk $Disk kept, unattached. Not accepted until guest_c1.sh rb and the fingerprints pass."
