# G3-A. No real data. Removes the PROD deployer's two project-wide bindings, guards guest DNS, and dry-runs the rehearsal on the blank synthetic disk.
# The project policy is saved first, and restore_deployer.ps1 puts both bindings back. It refuses a binding it doesn't expect, and any existing copy of the snapshot.
. "$PSScriptRoot\common.ps1"
$Dir = Join-Path $Here 'a'
New-Item -ItemType Directory -Force $Dir | Out-Null
function Done([string]$r, [int]$rc) { Write-Output "G3A $r"; [IO.File]::WriteAllText("$Dir\RESULT.txt", "$r`n"); exit $rc }
if (Test-Path "$Dir\started") { Write-Output 'G3A STOPPED already started'; exit 2 }   # never overwrites the first run's result
$found = @(Get-DeployerBindings)
$facts = ($found | ForEach-Object { "$($_.role) condition=$($_.condition)" }) -join '; '
foreach ($role in $Roles) { if (-not @($found | Where-Object { $_.role -eq $role -and -not $_.condition }).Count) { Done "STOPPED expected binding missing: $role" 2 } }
if (@($found | Where-Object { $Roles -notcontains $_.role -and $_.role -ne 'roles/compute.viewer' }).Count) { Done "STOPPED unexpected deployer role: $facts" 2 }
$r = Invoke-G @('compute', 'disks', 'list', "--project=$Project", '--format=json')
if ($r.Code -ne 0) { Done 'STOPPED disks list' 2 }
if (@(@($r.Text | ConvertFrom-Json) | Where-Object { $_.sourceSnapshot }).Count) { Done 'STOPPED a disk built from a snapshot exists' 2 }
New-Item -ItemType File "$Dir\started" | Out-Null
Invoke-G @('projects', 'get-iam-policy', $Project, '--format=json') "$Dir\policy-before.json" | Out-Null
foreach ($role in $Roles) {
    $r = Invoke-G @('projects', 'remove-iam-policy-binding', $Project, "--member=$Deployer", "--role=$role", '--condition=None', '--format=none') "$Dir\remove-$($role -replace '\W', '-').txt"
    if ($r.Code -ne 0) { Done "STOPPED remove $role rc $($r.Code)" 2 }
}
$left = @(Get-DeployerBindings | Where-Object { $Roles -contains $_.role })
if ($left.Count) { Done 'STOPPED binding still present' 2 }
$r = Invoke-Guest 'guest_dns_guard.sh' $null "$Dir\dns-guard.txt"
if ($r.Text -notmatch '(?m)^DNS_GUARD PASS') { Done 'STOPPED DNS guard' 2 }
foreach ($f in 'guest_rehearsal.sh', 'rehearsal_compare.py', 'app_old.py', 'app_new.py', 'fake_core.py') {
    $u = Invoke-G @('compute', 'scp', (Join-Path $Here $f), "${Vm}:/tmp/$f", "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet')
    if ($u.Code -ne 0 -and -not $env:G3_GCLOUD) { Done "STOPPED copy $f rc $($u.Code)" 2 }
}
$m = Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', '--command=sudo -n install -d -m 0700 /var/tmp/g3 && sudo -n mv /tmp/guest_rehearsal.sh /tmp/rehearsal_compare.py /tmp/app_old.py /tmp/app_new.py /tmp/fake_core.py /var/tmp/g3/ && sudo -n sed -i "s/\r$//" /var/tmp/g3/guest_rehearsal.sh && echo PLACED')
if ($m.Text -notmatch '(?m)^PLACED') { Done 'STOPPED files not placed' 2 }
$r = Invoke-Guest 'guest_rehearsal.sh' 'SYNTHETIC' "$Dir\dry-run.txt"
if ($r.Text -notmatch '(?m)^REHEARSAL PASS') { Done 'STOPPED dry run failed' 2 }
Done 'PASS' 0
