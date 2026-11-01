# Replaces the guest files on lilith-01 after the host-guard correction, and clears the spent preflight attempt so it can run once more (PREPARED, NOT APPROVED, NOT RUN).
# Needs APPROVED_PREPARE holding this manifest's digest, and the phrase. Changes only /var/tmp/c1. Stops at the first failure, with no retry.
param([Parameter(Mandatory = $true)][string]$Confirm)
. "$PSScriptRoot\common.ps1"
if ($Confirm -ne 'RESTAGE-CUTOVER1') { Write-Output 'RESTAGE REFUSED confirmation'; exit 3 }
$digest = (Get-FileHash "$Here\MANIFEST.txt" -Algorithm SHA256).Hash.ToLower()
if (-not (Test-Path "$Here\APPROVED_PREPARE") -or (Get-Content "$Here\APPROVED_PREPARE" -Raw).Trim() -ne $digest) { Write-Output 'RESTAGE REFUSED not approved'; exit 3 }
if (Test-Path "$Here\raw-attempt1") { Write-Output 'RESTAGE STOPPED already ran'; exit 2 }
$files = 'guest_c1.sh', 'live_compare.py', 'rehearsal_compare.py'
Push-Location $Here
foreach ($f in @($files) + 'stage_c1.sh') {
    $r = Invoke-G @('compute', 'scp', '--quiet', "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', $f, "${Vm}:/tmp/c1-$f")
    if ($r.Code -ne 0) { Pop-Location; Write-Output "RESTAGE STOPPED upload $f rc $($r.Code)"; exit 2 }
}
Pop-Location
$sums = ($files | ForEach-Object { (Get-FileHash (Join-Path $Here $_) -Algorithm SHA256).Hash.ToLower() }) -join ' '
$r = Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', "--command=sudo -n bash /tmp/c1-stage_c1.sh $sums")
if ($r.Text -notmatch '(?m)^STAGED') { Write-Output 'RESTAGE STOPPED guest files not confirmed'; exit 2 }
if (Test-Path "$Here\raw") { Move-Item "$Here\raw" "$Here\raw-attempt1" } else { New-Item -ItemType Directory "$Here\raw-attempt1" | Out-Null }
Write-Output 'RESTAGE PASS'
