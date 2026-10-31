# G3-A. No real data. Removes the PROD deployer's two project-wide bindings, guards guest DNS, and dry-runs the rehearsal on the blank synthetic disk.
# The project policy is captured and checked before any change. Any failure after a removal restores exactly the two bindings, unless a real-data copy exists or can't be ruled out.
. "$PSScriptRoot\common.ps1"
$Dir = Join-Path $Here 'a'
New-Item -ItemType Directory -Force $Dir | Out-Null
function Done([string]$r, [int]$rc) { Write-Output "G3A $r"; [IO.File]::WriteAllText("$Dir\RESULT.txt", "$r`n"); exit $rc }
function Recover([string]$why) { $outcome = Restore-Deployer; Done "STOPPED $why; RECOVERY $outcome" 2 }
function Policy-Lines([string]$json) {
    $lines = @()
    foreach ($b in (($json | ConvertFrom-Json).bindings)) { foreach ($m in $b.members) { $lines += "$($b.role) $m $([bool]$b.condition)" } }
    return @($lines | Sort-Object)
}
if (Test-Path "$Dir\started") { Write-Output 'G3A STOPPED already started'; exit 2 }   # never overwrites the first run's result
$lives = Invoke-G @('compute', 'instances', 'describe', $Vm, "--zone=$Zone", "--project=$Project", '--format=value(status)')
if ($lives.Code -ne 0 -or $lives.Text.Trim() -ne 'RUNNING') { Done 'STOPPED rehearsal VM not running' 2 }
try { $found = @(Get-DeployerBindings) } catch { Done 'STOPPED policy capture rc unreadable' 2 }
$facts = ($found | ForEach-Object { "$($_.role) condition=$($_.condition)" }) -join '; '
foreach ($role in $Roles) { if (-not @($found | Where-Object { $_.role -eq $role -and -not $_.condition }).Count) { Done "STOPPED expected binding missing: $role" 2 } }
if (@($found | Where-Object { $Roles -notcontains $_.role -and $_.role -ne 'roles/compute.viewer' }).Count) { Done "STOPPED unexpected deployer role: $facts" 2 }
if (-not (Test-NoRealCopy)) { Done 'STOPPED a real-data copy exists or could not be ruled out' 2 }
# Capture the policy, and prove the saved file before any change
$pol = Invoke-G @('projects', 'get-iam-policy', $Project, '--format=json')
if ($pol.Code -ne 0) { Done "STOPPED policy capture rc $($pol.Code)" 2 }
[IO.File]::WriteAllText("$Dir\policy-before.json", $pol.Text)
try {
    $saved = Get-Content "$Dir\policy-before.json" -Raw
    $before = @(Policy-Lines $saved)
} catch { Done 'STOPPED saved policy does not parse' 2 }
foreach ($role in $Roles) { if ($before -notcontains "$role $Deployer False") { Done "STOPPED saved policy lacks $role" 2 } }
if (-not @($before | Where-Object { $_ -like 'roles/owner user:*' }).Count) { Done 'STOPPED saved policy has no owner' 2 }
$check = Invoke-G @('projects', 'get-iam-policy', $Project, '--format=json')
if ($check.Code -ne 0 -or ((@(Policy-Lines $check.Text) -join '|') -ne ($before -join '|'))) { Done 'STOPPED policy moved during capture' 2 }
[IO.File]::WriteAllText("$Dir\policy-before.sha256", (Get-FileHash "$Dir\policy-before.json" -Algorithm SHA256).Hash.ToLower() + "`n")
New-Item -ItemType File "$Dir\started" | Out-Null
try {
foreach ($role in $Roles) {
    $r = Invoke-G @('projects', 'remove-iam-policy-binding', $Project, "--member=$Deployer", "--role=$role", '--condition=None', '--format=none') "$Dir\remove-$($role -replace '\W', '-').txt"
    if ($r.Code -ne 0) { Recover "remove $role rc $($r.Code)" }
}
$after = Invoke-G @('projects', 'get-iam-policy', $Project, '--format=json')
if ($after.Code -ne 0) { Recover 'policy read after removal' }
$want = @($before | Where-Object { $_ -ne "roles/iap.tunnelResourceAccessor $Deployer False" -and $_ -ne "roles/compute.osAdminLogin $Deployer False" })
if ((@(Policy-Lines $after.Text) -join '|') -ne ($want -join '|')) { Recover 'policy differs from the two approved removals' }
# Owner and rehearsal access still work, proved by logging in
$a = Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', '--command=sudo -n id -u && echo OWNER_ACCESS_OK') "$Dir\owner-access.txt"
if ($a.Text -notmatch '(?m)^OWNER_ACCESS_OK') { Recover 'owner access to the rehearsal VM' }
$r = Invoke-Guest 'guest_dns_guard.sh' $null "$Dir\dns-guard.txt"
if ($r.Text -notmatch '(?m)^DNS_GUARD APPLIED') { Recover 'DNS guard' }
$r = Invoke-Guest 'guest_dns_check.sh' $null "$Dir\dns-check.txt"
if ($r.Text -notmatch '(?m)^DNS_CHECK PASS') { Recover 'DNS check' }
foreach ($f in 'guest_rehearsal.sh', 'guest_dns_check.sh', 'rehearsal_compare.py', 'app_old.py', 'app_new.py', 'fake_core.py') {
    $u = Invoke-G @('compute', 'scp', (Join-Path $Here $f), "${Vm}:/tmp/$f", "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet')
    if ($u.Code -ne 0) { Recover "copy $f rc $($u.Code)" }
}
$m = Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', '--command=sudo -n install -d -m 0700 /var/tmp/g3 && sudo -n mv /tmp/guest_rehearsal.sh /tmp/guest_dns_check.sh /tmp/rehearsal_compare.py /tmp/app_old.py /tmp/app_new.py /tmp/fake_core.py /var/tmp/g3/ && sudo -n sed -i "s/\r$//" /var/tmp/g3/guest_rehearsal.sh /var/tmp/g3/guest_dns_check.sh && echo PLACED')
if ($m.Text -notmatch '(?m)^PLACED') { Recover 'files not placed' }
$r = Invoke-Guest 'guest_rehearsal.sh' 'SYNTHETIC' "$Dir\dry-run.txt"
if ($r.Text -notmatch '(?m)^REHEARSAL PASS') { Recover 'dry run failed' }
} catch { Recover "exception $($_.Exception.Message)" }
Done 'PASS' 0
