# Run locally in PowerShell. Connection input is hidden and never written to disk.
[CmdletBinding()]
param(
    [string]$Dataset = 'ramosolo-demo-v1',
    [string]$HandoffDirectory = 'C:\Temp\ramosolo-demo-v1-private'
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$originalValues = @{}
foreach ($key in @('DATABASE_URL', 'DB_SCHEMA', 'PYTHON_DOTENV_DISABLED')) {
    $originalValues[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}
$secureConnection = $null
$connectionPointer = [IntPtr]::Zero
try {
    if (-not [Environment]::GetEnvironmentVariable('DATABASE_URL', 'Process') -and
        -not [Environment]::GetEnvironmentVariable('SUPABASE_DB_URL', 'Process')) {
        $secureConnection = Read-Host 'Supabase PostgreSQL connection URL from Connect (hidden input)' -AsSecureString
        $connectionPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureConnection)
        $env:DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($connectionPointer)
    }
    $env:DB_SCHEMA = 'ramosolo'
    $env:PYTHON_DOTENV_DISABLED = '1'
    Push-Location -LiteralPath $projectRoot
    try {
        & python -m flask --app app:create_app check-connections --only database
        if ($LASTEXITCODE -ne 0) { throw 'Database connection check failed.' }
        $firstCounts = $null
        foreach ($run in 1..2) {
            $seedOutput = & python -m flask --app app:create_app seed-demo --dataset $Dataset --expected-project mavpwgqjgjnvopnnqnmb --handoff-directory $HandoffDirectory --diagnose-schema
            if ($LASTEXITCODE -ne 0) { throw 'Hosted seed stopped. Review the sanitized output.' }
            $seedOutput | Write-Output
            $seedText = $seedOutput -join "`n"
            $result = $seedText.Substring(0, $seedText.LastIndexOf('}') + 1) | ConvertFrom-Json
            $recordCounts = $result.counts | ConvertTo-Json -Compress
            if ($run -eq 1) { $firstCounts = $recordCounts }
            elseif ($recordCounts -ne $firstCounts) { throw 'Dataset table counts changed on repeat seed.' }
        }
        Write-Output 'Dataset counts are stable across both hosted seed runs.'
        & python -m flask --app app:create_app verify-demo --dataset $Dataset --expected-project mavpwgqjgjnvopnnqnmb --handoff-file (Join-Path $HandoffDirectory 'accounts.json')
        if ($LASTEXITCODE -ne 0) { throw 'Hosted login and isolation verification failed.' }
    } finally {
        Pop-Location
    }
} finally {
    foreach ($key in $originalValues.Keys) {
        [Environment]::SetEnvironmentVariable($key, $originalValues[$key], 'Process')
    }
    if ($connectionPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($connectionPointer)
    }
    if ($null -ne $secureConnection) { $secureConnection.Dispose() }
}
