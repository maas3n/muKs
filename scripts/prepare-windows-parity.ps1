# Build from the exact approved Linux v0.0.3 source, but modify only Windows tool lookup.
$ErrorActionPreference = 'Stop'
$repo = $env:GITHUB_REPOSITORY
if ($repo -ne 'maas3n/muKs') { throw "Refusing unexpected repository $repo" }
$root = Join-Path $env:RUNNER_TEMP 'exact-muksmatt-v0.0.3'
New-Item -ItemType Directory -Force -Path $root | Out-Null
gh release download v0.0.3 --repo $repo --pattern muKsMaTT-0.0.3-Source.tar.gz --dir $root
if ($LASTEXITCODE -ne 0) { throw 'Unable to download original v0.0.3 source' }
$archive = Join-Path $root 'muKsMaTT-0.0.3-Source.tar.gz'
$got = (Get-FileHash -Algorithm SHA256 $archive).Hash.ToLowerInvariant()
if ($got -ne 'd36d9e4128d0a9432d3da4916c5de7777208f0faf578d83b7f6c24055b5cbe10') {
    throw "v0.0.3 source SHA256 mismatch: $got"
}
tar -xzf $archive -C $root
if ($LASTEXITCODE -ne 0) { throw 'Original source archive extraction failed' }
$source = Join-Path $root 'muKsMaTT-0.0.3-Source'
if (-not (Test-Path (Join-Path $source 'src/app_windows_3.go'))) { throw 'Unexpected original source layout' }
python (Join-Path $env:GITHUB_WORKSPACE 'scripts/apply-windows-parity.py') $source
if ($LASTEXITCODE -ne 0) { throw 'Strict Windows-only source patch failed' }

$env:CGO_ENABLED = '0'
$env:GOOS = 'windows'
$env:GOARCH = 'amd64'
Push-Location (Join-Path $source 'src')
try {
    go test -count=1 ./...
    if ($LASTEXITCODE -ne 0) { throw 'Native Windows Go tests failed' }
    go test -tags cli -count=1 ./...
    if ($LASTEXITCODE -ne 0) { throw 'Native Windows CLI tests failed' }
    go vet ./...
    if ($LASTEXITCODE -ne 0) { throw 'Native Windows go vet failed' }

    $stage = Join-Path $env:RUNNER_TEMP 'muKsMaTT-v0.0.3-Windows-parity-TEST'
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    go build -trimpath -buildvcs=false -ldflags '-s -w -H=windowsgui -X main.appVersion=0.0.3-windows-parity-test' -o (Join-Path $stage 'muksmatt.exe') .
    if ($LASTEXITCODE -ne 0) { throw 'Native Windows GUI compilation failed' }
    go build -tags cli -trimpath -buildvcs=false -ldflags '-s -w -X main.appVersion=0.0.3-windows-parity-test' -o (Join-Path $stage 'muksmatt-cli.exe') .
    if ($LASTEXITCODE -ne 0) { throw 'Native Windows console CLI compilation failed' }
    Copy-Item 'muksmatt.exe.manifest' (Join-Path $stage 'muksmatt.exe.manifest')
} finally {
    Pop-Location
}

# The same verified BtbN FFmpeg commit and MediaInfo version as Linux,
# downloaded ONLY during CI and physically included in the portable ZIP.
python (Join-Path $env:GITHUB_WORKSPACE 'scripts/stage-windows-parity-media.py') --source $source --dest $stage
if ($LASTEXITCODE -ne 0) { throw 'Pinned FFmpeg / MediaInfo staging failed' }
foreach ($item in @('tools/ffmpeg-2026-09-08/ffmpeg.exe','tools/ffmpeg-2026-09-08/ffprobe.exe','tools/mediainfo-26.05/MediaInfo.exe','WINDOWS-THIRD-PARTY-LOCK.json')) {
    if (-not (Test-Path (Join-Path $stage $item))) { throw "Missing required Windows bundled media component: $item" }
}
"PARITY_SOURCE=$source" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"PARITY_STAGE=$stage" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
Write-Host 'PASS: Windows GUI/CLI tests and builds; bundled verified FFmpeg/FFprobe/MediaInfo, no Linux source changes'
