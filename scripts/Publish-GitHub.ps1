param(
    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$Repository = 'VoiceTrigger',
    [switch]$EnablePages
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
Set-Location -LiteralPath $root

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE"
    }
}

Get-Command gh, git -ErrorAction Stop | Out-Null
Invoke-Checked -Executable gh -Arguments @('auth', 'status')
$login = & gh api user --jq .login
if ($LASTEXITCODE -ne 0 -or -not $login) {
    throw 'Cannot determine the authenticated GitHub account'
}
$identityName = & git config --get user.name
$identityEmail = & git config --get user.email
if (-not $identityName -or -not $identityEmail) {
    throw 'Configure your own git user.name and user.email before publishing'
}
if (Test-Path -LiteralPath (Join-Path $root '.git')) {
    throw 'A Git repository already exists. Inspect its status and remote before publishing manually; this script never overwrites or force-pushes it.'
}

$publishPaths = @(
    'README.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md',
    'pyproject.toml', 'MANIFEST.in', 'Dockerfile', 'compose.yaml', 'mkdocs.yml',
    'config.example.toml', '.env.example', '.gitignore', '.dockerignore',
    'src', 'tests', 'docs', 'schemas', 'scripts', '.github'
)
foreach ($path in $publishPaths) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $path))) {
        throw "Missing publication file: $path"
    }
}
Invoke-Checked -Executable git -Arguments @('init', '-b', 'main')
Invoke-Checked -Executable git -Arguments (@('add', '--') + $publishPaths)
$tracked = & git ls-files
if ($LASTEXITCODE -ne 0) {
    throw 'Cannot inspect staged files'
}
foreach ($path in $tracked) {
    if ($path -match '(^|/)(\.env|config\.local\.toml|models|events|\.venv|__pycache__)(/|$)' -or $path -match '\.(wav|mp3|mp4|tar)$') {
        throw "Refusing to publish a private/generated file: $path"
    }
}
Invoke-Checked -Executable git -Arguments @('diff', '--cached', '--check')
Invoke-Checked -Executable git -Arguments @('commit', '-m', 'Initial VoiceTrigger implementation, documentation and CI')
$fullName = "$login/$Repository"
Invoke-Checked -Executable gh -Arguments @(
    'repo', 'create', $fullName, '--public', '--source', $root,
    '--remote', 'origin', '--push', '--description',
    'Local continuous voice keyword detection with Tesla P4 Docker deployment'
)

if ($EnablePages) {
    Invoke-Checked -Executable gh -Arguments @('api', '--method', 'POST', "repos/$fullName/pages", '-f', 'build_type=workflow')
    Invoke-Checked -Executable gh -Arguments @('variable', 'set', 'PUBLISH_DOCS', '--body', 'true', '--repo', $fullName)
    Invoke-Checked -Executable gh -Arguments @('workflow', 'run', 'docs.yml', '--repo', $fullName)
}
Invoke-Checked -Executable gh -Arguments @('repo', 'view', $fullName, '--json', 'url,isPrivate', '--jq', '. | {url, isPrivate}')
Write-Output 'Publication requested. Check GitHub Actions; this script does not claim CI or Pages deployment has passed.'
