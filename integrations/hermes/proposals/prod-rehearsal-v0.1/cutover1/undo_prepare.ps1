# Reverses prepare.ps1, whatever it reached (PREPARED, NOT APPROVED, NOT RUN). Each step is attempted; a step that had nothing to do is harmless. Never touches a snapshot, including any the schedule has already taken.
param([Parameter(Mandatory = $true)][string]$Confirm)
. "$PSScriptRoot\common.ps1"
if ($Confirm -ne 'UNDO-PREPARE') { Write-Output 'UNDO REFUSED confirmation'; exit 3 }
New-Item -ItemType Directory -Force $Out | Out-Null
$bad = 0
function Step([string]$Name, [string[]]$A) { $r = Invoke-G $A; Write-Output "$Name rc $($r.Code)"; if ($r.Code -ne 0) { $script:bad++ } }
Step 'schedule detach' @('compute', 'disks', 'remove-resource-policies', $Disk, "--zone=$Zone", "--project=$Project", "--resource-policies=$Schedule", '--format=none')
Step 'schedule delete' @('compute', 'resource-policies', 'delete', $Schedule, "--region=$Region", "--project=$Project", '--quiet', '--format=none')
$p = Get-TunnelPolicy
Invoke-Iap 'setIamPolicy' @{ policy = @{ version = 3; etag = $p.etag; bindings = @() } } | Out-Null
if (@((Get-TunnelPolicy).bindings | Where-Object { $_ }).Count) { Write-Output 'tunnel policy not empty'; $bad++ } else { Write-Output 'tunnel policy empty' }
Step 'login remove' @('compute', 'instances', 'remove-iam-policy-binding', $Vm, "--zone=$Zone", "--project=$Project", "--member=$Deployer", '--role=roles/compute.osAdminLogin', '--format=none')
Step 'firewall target' @('compute', 'firewall-rules', 'update', $Rule, '--target-tags=', "--project=$Project", '--format=none')
if ($bad) { Write-Output "UNDO INCOMPLETE $bad"; exit 2 }
Write-Output 'UNDO PASS'
