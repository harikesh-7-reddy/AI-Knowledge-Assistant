$ErrorActionPreference = 'Stop'
$envPath = Join-Path $PSScriptRoot '.env'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

if (Test-Path $envPath) {
    $backupPath = "$envPath.backup-$timestamp"
    Copy-Item $envPath $backupPath
    $lines = Get-Content -Path $envPath
} else {
    $backupPath = $null
    $lines = @()
}

$existingGeminiKey = ''
foreach ($line in $lines) {
    if ($line -match '^\s*GEMINI_API_KEY\s*=\s*(.*)$') {
        $existingGeminiKey = $Matches[1].Trim().Trim('"').Trim("'")
    }
}

# Preserve all unrelated configuration (JWT secret, paths, CORS, upload limits).
# Remove old provider-specific names; an OpenAI/Perplexity key is not a Gemini key.
$preserved = @($lines | Where-Object {
    $_ -notmatch '^\s*(OPENAI_API_KEY|OPENAI_CHAT_MODEL|OPENAI_EMBEDDING_MODEL|GEMINI_API_KEY|GEMINI_CHAT_MODEL|GEMINI_EMBEDDING_MODEL|GEMINI_EMBEDDING_DIMENSION)\s*='
})

$geminiLines = @(
    "GEMINI_API_KEY=$existingGeminiKey",
    'GEMINI_CHAT_MODEL=gemini-3.6-flash',
    'GEMINI_EMBEDDING_MODEL=gemini-embedding-001',
    'GEMINI_EMBEDDING_DIMENSION=3072'
)
$newLines = @($preserved + '' + '# Gemini Developer API settings' + $geminiLines)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($envPath, [string[]]$newLines, $utf8NoBom)

Write-Host 'Gemini environment configuration prepared.' -ForegroundColor Green
if ($backupPath) { Write-Host "Previous .env backed up to: $backupPath" }
if ([string]::IsNullOrWhiteSpace($existingGeminiKey)) {
    Write-Host 'Add your Google AI Studio key to GEMINI_API_KEY in backend/.env.' -ForegroundColor Yellow
} else {
    Write-Host 'Existing GEMINI_API_KEY value preserved.' -ForegroundColor Green
}
Write-Host 'Unrelated environment settings were preserved. No database or uploads were changed.'
