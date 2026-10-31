# Puts the two PROD deployer bindings back. Only on the owner's approval, and never while a copy of real data exists: Cutover 1 grants narrower access instead.
param([Parameter(Mandatory = $true)][string]$ConfirmRestore)
. "$PSScriptRoot\common.ps1"
if ($ConfirmRestore -ne 'RESTORE-DEPLOYER') { Write-Output 'REFUSED confirmation'; exit 3 }
$r = Invoke-G @('compute', 'disks', 'list', "--project=$Project", '--format=json')
if ($r.Code -ne 0) { Write-Output 'STOPPED disks list'; exit 2 }
if (@(@($r.Text | ConvertFrom-Json) | Where-Object { $_.name -eq $Copy }).Count) { Write-Output 'REFUSED the real-data copy still exists'; exit 3 }
foreach ($role in $Roles) {
    $r = Invoke-G @('projects', 'add-iam-policy-binding', $Project, "--member=$Deployer", "--role=$role", '--condition=None', '--format=none')
    if ($r.Code -ne 0) { Write-Output "STOPPED $role rc $($r.Code)"; exit 2 }
}
Write-Output 'RESTORED'
