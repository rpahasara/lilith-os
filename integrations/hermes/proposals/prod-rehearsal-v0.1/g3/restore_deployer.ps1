# Puts the two PROD deployer bindings back. Only on the owner's approval, and never while a copy of real data exists: Cutover 1 grants narrower access instead.
param([Parameter(Mandatory = $true)][string]$ConfirmRestore)
. "$PSScriptRoot\common.ps1"
if ($ConfirmRestore -ne 'RESTORE-DEPLOYER') { Write-Output 'REFUSED confirmation'; exit 3 }
$r = Restore-Deployer
Write-Output $r
if ($r -ne 'RESTORED') { exit 2 }
