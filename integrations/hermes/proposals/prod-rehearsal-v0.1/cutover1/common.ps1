# Cutover 1 shared constants. Dot-sourced. Defines no actions.
$ErrorActionPreference = 'Stop'
$G = if ($env:C1_GCLOUD) { $env:C1_GCLOUD } else { 'C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' }
$Project = 'lilith-agent-260823-27389'; $ProjectNumber = '763184673487'; $Zone = 'asia-southeast1-b'; $Region = 'asia-southeast1'
$Vm = 'lilith-01'; $Disk = 'lilith-01'; $Rule = 'lilith-api-iap'; $Tag = 'lilith-vm'; $Schedule = 'lilith-01-daily'
$Deployer = 'serviceAccount:github-lilith-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com'
$Here = $PSScriptRoot
$Out = Join-Path $Here 'prepare'
$TunnelUrl = "https://iap.googleapis.com/v1/projects/$ProjectNumber/iap_tunnel/zones/$Zone/instances/$Vm"

function Invoke-G([string[]]$GArgs) {
    $saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $o = & $G @GArgs 2>&1
    $c = $LASTEXITCODE
    $ErrorActionPreference = $saved
    return @{ Code = $c; Text = ($o | Out-String) }
}

function Invoke-Iap([string]$Method, $Body) {
    # Instance tunnel policy: gcloud has no command for it. A test sets C1_IAP to a stand-in. The token stays in this process.
    if ($env:C1_IAP) { return (& $env:C1_IAP $Method ($Body | ConvertTo-Json -Depth 8 -Compress)) | ConvertFrom-Json }
    $t = ((& $G auth print-access-token) | Out-String).Trim()
    return Invoke-RestMethod -Method Post -Uri "${TunnelUrl}:$Method" -Headers @{ Authorization = "Bearer $t" } -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Depth 8 -Compress)
}

function Get-TunnelPolicy { return Invoke-Iap 'getIamPolicy' @{ options = @{ requestedPolicyVersion = 3 } } }

function Get-DeployerRoles {
    $r = Invoke-G @('projects', 'get-iam-policy', $Project, '--format=json')
    if ($r.Code -ne 0) { throw 'project policy read failed' }
    return @(@(($r.Text | ConvertFrom-Json).bindings) | Where-Object { $_.members -contains $Deployer } | ForEach-Object { $_.role })
}

function Stop-Here([string]$Reason, [int]$Rc = 2) {
    Write-Output "PREPARE $Reason"
    [IO.File]::WriteAllText("$Out\RESULT.txt", "$Reason`n")
    exit $Rc
}
