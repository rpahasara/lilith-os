# Command Center credentials (PREPARED, NOT APPROVED, NOT RUN). The OWNER runs this, after the window. Copies the two PROD tokens into the gitignored .env.local for the Next server. Prints no token.
# Refuses direct mode: a browser can't hold a credential. Starting the Next server again is what loads them.
param([string]$EnvFile = 'C:\Users\edufo\Documents\Projects\lilith-os\.env.local')
. "$PSScriptRoot\common.ps1"
$lines = if (Test-Path $EnvFile) { @(Get-Content $EnvFile) } else { @() }
if ($lines -match '^\s*NEXT_PUBLIC_LILITH_API_URL\s*=') { Write-Output 'CC REFUSED direct mode is set: remove NEXT_PUBLIC_LILITH_API_URL'; exit 3 }
if (-not ($lines -match '^\s*LILITH_API_URL\s*=\s*\S')) { Write-Output 'CC REFUSED LILITH_API_URL is not set'; exit 3 }
$r = Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', '--command=sudo -n cat /etc/lilith-os-api/auth.env')
$read = [regex]::Match($r.Text, '(?m)^LILITH_OS_READ_TOKEN=([0-9a-f]{64})\s*$').Groups[1].Value
$write = [regex]::Match($r.Text, '(?m)^LILITH_OS_WRITE_TOKEN=([0-9a-f]{64})\s*$').Groups[1].Value
Remove-Variable r
if (-not $read -or -not $write) { Write-Output 'CC STOPPED tokens not read'; exit 2 }
$keep = @($lines | Where-Object { $_ -notmatch '^\s*LILITH_OS_(READ|WRITE)_TOKEN\s*=' })
$new = $keep + @("LILITH_OS_READ_TOKEN=$read", "LILITH_OS_WRITE_TOKEN=$write")
[IO.File]::WriteAllText("$EnvFile.new", (($new -join "`n") + "`n"))
Move-Item -Force "$EnvFile.new" $EnvFile
Write-Output 'CC PASS tokens written. Open the tunnel to lilith-01, then restart the Next server.'
