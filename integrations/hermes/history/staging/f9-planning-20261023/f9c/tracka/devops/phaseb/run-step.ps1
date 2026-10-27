param([Parameter(Mandatory)][string]$Step, [string]$Env = "")
# Runs one Phase B step script as root on lilith-dev-01 ONLY (IAP SSH), gzip+base64 embedded in --command (never stdin).
# Output is saved locally as <step>.out; the remote script also tees it to /var/tmp/f8/f9c2-run/<step>.out for re-read.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bash = "C:\Program Files\Git\usr\bin\bash.exe"
$unix = (Join-Path $here "$Step.sh") -replace '\\','/' -replace '^([A-Za-z]):', '/$1'
$b64 = (& $bash -lc "sed 's/\r$//' '$unix' | gzip -9n | base64 -w0").Trim()
if ($b64.Length -gt 7000) { throw "script too large for --command ($($b64.Length))" }
$sha = (& $bash -lc "echo '$b64' | base64 -d | gunzip | sha256sum | cut -c1-16").Trim()
$out = Join-Path $here "$Step.out"
$g = "C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
& $g compute ssh lilith-dev-01 --zone=asia-southeast1-b --project=lilith-agent-260823-27389 --tunnel-through-iap --quiet `
  --command "echo $b64 | base64 -d | gunzip | sudo -n env $Env bash" 2>&1 | Out-File -Encoding utf8 $out
"rc=$LASTEXITCODE script_sha=$sha"
Get-Content $out
