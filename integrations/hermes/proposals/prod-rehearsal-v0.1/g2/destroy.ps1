# G2 teardown. DESTRUCTIVE: needs its own owner approval, and the -Confirm value. Removes only the exact G2 resources, never a snapshot.
# Refuses while anything but the synthetic disk is attached, because at G3 that disk would hold real data and has its own destruction procedure.
param([Parameter(Mandatory = $true)][string]$ConfirmDestroy)
. "$PSScriptRoot\common.ps1"
if ($ConfirmDestroy -ne 'DESTROY-G2-20261101') { Write-Output 'REFUSED confirmation'; exit 3 }
$r = Invoke-G @('compute', 'instances', 'describe', $Vm, "--zone=$Zone", "--project=$Project", '--format=json')
if ($r.Code -eq 0) {
    $i = $r.Text | ConvertFrom-Json
    $other = @(@($i.disks) | Where-Object { -not $_.boot -and (($_.source -split '/')[-1]) -ne $Synth })
    if ($other.Count) { Write-Output 'REFUSED a non-synthetic disk is attached'; exit 3 }
}
foreach ($c in @(
    @('compute', 'instances', 'delete', $Vm, "--zone=$Zone", "--project=$Project", '--quiet'),
    @('compute', 'disks', 'delete', $Synth, "--zone=$Zone", "--project=$Project", '--quiet'),
    @('compute', 'firewall-rules', 'delete', $RuleIap, "--project=$Project", '--quiet'),
    @('compute', 'firewall-rules', 'delete', $RuleDeny, "--project=$Project", '--quiet'),
    @('compute', 'networks', 'subnets', 'delete', $Subnet, "--region=$Region", "--project=$Project", '--quiet'),
    @('compute', 'networks', 'delete', $Net, "--project=$Project", '--quiet'))) {
    $r = Invoke-G $c
    Write-Output "$($c[1..2] -join ' ') rc $($r.Code)"
    if ($r.Code -ne 0) { Write-Output 'STOPPED'; exit 2 }
}
Write-Output 'DESTROYED'
