# Verify the bundled Windows parity build, execute real authored DVD operations,
# smoke-test the GUI offline, and package a fully checked private trial ZIP.
$ErrorActionPreference = 'Stop'
$stage = $env:PARITY_STAGE
if (-not $stage -or -not (Test-Path $stage)) { throw 'Windows parity staging directory missing' }
$repo = $env:GITHUB_WORKSPACE

python (Join-Path $repo 'scripts/stage-windows-parity-dlls.py') --helper (Join-Path $stage 'muksmatt-bluray-nav.exe') --mingw-bin $env:PARITY_MINGW_BIN --objdump $env:PARITY_OBJDUMP --dest $stage --ffmpeg-dir (Join-Path $stage 'tools/ffmpeg-2026-09-08')
if ($LASTEXITCODE -ne 0) { throw 'Native DVD and Blu-ray DLL staging failed' }
$navOutput = (& (Join-Path $stage 'muksmatt-bluray-nav.exe') --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $navOutput -ne 'MUKSMATT_BD_NAV_1') {
    throw "Bundled native Blu-ray helper could not load version-matched DLLs: $navOutput"
}

# No first-use network fetching: any attempt to use the old downloader must
# fail through the deliberately unavailable proxy. All tests use ZIP tools.
$env:HTTP_PROXY = 'http://127.0.0.1:9'
$env:HTTPS_PROXY = 'http://127.0.0.1:9'
$env:ALL_PROXY = 'http://127.0.0.1:9'

$cli = Join-Path $stage 'muksmatt-cli.exe'
$version = (& $cli --version | Out-String)
if ($LASTEXITCODE -ne 0 -or -not $version.Contains('0.0.3-windows-parity-test')) {
    throw "Incorrect Windows parity CLI version: $version"
}
$help = (& $cli --help | Out-String)
if ($LASTEXITCODE -ne 0) { throw 'CLI --help failed' }
foreach ($token in @('scan SOURCE','metadata','remux','demux','advanced demux','bluray scan','bluray tracks','bluray remux','bluray demux','--batch','--version')) {
    if (-not $help.Contains($token)) { throw "Existing Linux command missing on Windows: $token" }
}
foreach ($argsList in @(@('demux','--help'),@('advanced','demux','--help'),@('bluray','scan','--help'),@('bluray','tracks','--help'),@('bluray','remux','--help'),@('bluray','demux','--help'))) {
    $helpResult = (& $cli @argsList 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $helpResult -notmatch '(?i)Usage(:| of )') {
        throw "Windows CLI help/flag routing failed: $($argsList -join ' ')"
    }
}
foreach ($cmd in @('tools', 'doctor')) {
    $output = (& $cli $cmd 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $output -notmatch 'FFmpeg:') {
        throw "Offline bundled-tool diagnostic failed: $cmd $output"
    }
}
Write-Host 'PASS: Windows CLI routing and bundled media diagnostics work with no internet'

$folder = Join-Path $repo 'authored-dvd'
$ifo = Get-ChildItem $folder -Recurse -Filter 'VIDEO_TS.IFO' | Select-Object -First 1
if (-not $ifo) { throw 'Linux-authored DVD regression fixture missing' }
$dvd = Split-Path (Split-Path $ifo.FullName -Parent) -Parent
$out = Join-Path $env:RUNNER_TEMP 'Windows-actual-DVD-output'
$main = Join-Path $out 'main'
$advanced = Join-Path $out 'advanced'
$remux = Join-Path $out 'remux'
New-Item -ItemType Directory -Force -Path $main,$advanced,$remux | Out-Null

& $cli scan $dvd
if ($LASTEXITCODE -ne 0) { throw 'Windows DVD scan failed with bundled tools' }
& $cli metadata --title 1 $dvd
if ($LASTEXITCODE -ne 0) { throw 'Windows DVD metadata failed with bundled FFprobe' }
& $cli demux --title 1 --output $main --video mpeg2 $dvd
if ($LASTEXITCODE -ne 0) { throw 'Windows Main DVD DEMUX failed' }
& $cli advanced demux --title 1 --output $advanced --video mpeg2 $dvd
if ($LASTEXITCODE -ne 0) { throw 'Windows ADVANCED DVD DEMUX failed' }
& $cli remux --title 1 --output $remux $dvd
if ($LASTEXITCODE -ne 0) { throw 'Existing Windows DVD REMUX failed' }
foreach ($directory in @($main, $advanced)) {
    if (-not (Get-ChildItem $directory -Recurse -Filter '*.mpeg2' | Select-Object -First 1)) {
        throw "DVD DEMUX failed to output MPEG-2 elementary video in $directory"
    }
    if (-not (Get-ChildItem $directory -Recurse -Filter '*.ac3' | Select-Object -First 1)) {
        throw "DVD DEMUX failed to output AC-3 elementary audio in $directory"
    }
    if (Get-ChildItem $directory -Recurse -Filter '*.mkv') {
        throw "DVD DEMUX unexpectedly created intermediate MKV in $directory"
    }
}
if (-not (Get-ChildItem $remux -Recurse -Filter '*.mkv' | Select-Object -First 1)) {
    throw 'DVD REMUX failed to create MKV'
}
Write-Host 'PASS: real authored DVD scan, metadata, REMUX and BOTH DEMUX workflows, offline'

$gui = Join-Path $stage 'muksmatt.exe'
$p = Start-Process -FilePath $gui -WorkingDirectory $stage -PassThru
try {
    Start-Sleep -Seconds 6
    $p.Refresh()
    if ($p.HasExited) { throw "Windows GUI process exited early: $($p.ExitCode)" }
    Write-Host 'PASS: original Windows GUI starts with bundled tools and offline proxy'
} finally {
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
}

$readme = @'
muKsMaTT v0.0.3 - EXPERIMENTAL WINDOWS 64-BIT PARITY TEST BUILD

Windows build is based on exact SHA256-verified Linux v0.0.3 source.
Shared DVD/Blu-ray media-processing engines, CLI and Linux code are unchanged.
Only Windows-specific tool location was modified. ALL tools below are INCLUDED,
and the app DOES NOT download them on first launch.

Matching Linux upstream versions:
 - FFmpeg / FFprobe: N-126479-g08cd8df29d (2026-09-08)
 - MediaInfo: 26.05
 - libbluray: 1.3.4
 - libaacs: 0.11.1
 - libbdplus: 0.2.0
 - libdvdcss: 1.6.0
 - Native muKsMaTT Blu-ray navigator and all dependent DLLs

Linux's libudfread 1.1.2 support still needs validation on real Blu-ray
ISO/optical drives using Windows-native libraries. Linux's X11/Mesa graphics
libraries are not meaningful on Windows, which uses the existing Win32 GUI.

EXTRACT THE FULL ZIP TO A WRITABLE FOLDER. Do not start executables inside ZIP.
- GUI: double-click muksmatt.exe
- CLI: open PowerShell in folder and run:
  .\muksmatt-cli.exe --help
  .\muksmatt-cli.exe --version
  .\muksmatt-cli.exe tools
  .\muksmatt-cli.exe scan "D:\VIDEO_TS"
  .\muksmatt-cli.exe remux --title 1 --output "C:\Videos" "D:\VIDEO_TS"
  .\muksmatt-cli.exe demux --title 1 --output "C:\Videos" "D:\VIDEO_TS"
  .\muksmatt-cli.exe advanced demux --title 1 --output "C:\Videos" "D:\VIDEO_TS"
  .\muksmatt-cli.exe bluray scan "D:\BDMV"
  .\muksmatt-cli.exe bluray tracks --playlist 00800 "D:\BDMV"
  .\muksmatt-cli.exe bluray demux --playlist 00800 --output "C:\Videos" "D:\BDMV"

References: WINDOWS-THIRD-PARTY-LOCK.json, WINDOWS-MEDIA-DEPENDENCIES.json,
WINDOWS-NATIVE-PACKAGE-VERSIONS.txt, THIRD-PARTY-NOTICES.txt, SHA256SUMS.txt.

PRIVATE TEST ONLY: no approved Windows release. Actual Blu-ray ISO,
optical-drive, and protected DVD behaviors require owner testing.
'@
Set-Content -Path (Join-Path $stage 'README-WINDOWS.txt') -Value $readme -Encoding utf8
$notices = @'
Third-party media runtime: versions matched against verified Linux v0.0.3.
FFmpeg / FFprobe GPL build: BtbN FFmpeg-Builds
 https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-09-08-23-15
MediaInfo CLI 26.05:
 https://mediaarea.net/download/binary/mediainfo/26.05/
libbluray 1.3.4 / libaacs 0.11.1 / libbdplus 0.2.0 / libdvdcss 1.6.0:
 https://repo.msys2.org/mingw/mingw64/
Native libraries use matching Windows DLLs, not Linux ELF binaries.
Copyright notices and accompanying licenses are under licenses/.
No BDInfo or bdinfo-rs components are introduced.
'@
Set-Content -Path (Join-Path $stage 'THIRD-PARTY-NOTICES.txt') -Value $notices -Encoding utf8

$hashLines = foreach ($file in (Get-ChildItem $stage -Recurse -File | Sort-Object FullName)) {
    $rel = $file.FullName.Substring($stage.Length+1).Replace('\','/')
    "$((Get-FileHash -Algorithm SHA256 $file.FullName).Hash.ToLowerInvariant())  $rel"
}
Set-Content -Path (Join-Path $stage 'SHA256SUMS.txt') -Value $hashLines -Encoding ascii
$dist = Join-Path $repo 'dist'
New-Item -ItemType Directory -Force $dist | Out-Null
$zip = Join-Path $dist 'muKsMaTT-0.0.3-Windows-amd64-FULL-PARITY-TEST.zip'
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal
if (-not (Test-Path $zip)) { throw 'No portable Windows bundle ZIP generated' }
$verifyRoot = Join-Path $env:RUNNER_TEMP 'verify-windows-parity-zip'
Expand-Archive -Path $zip -DestinationPath $verifyRoot
foreach ($item in @('muksmatt.exe','muksmatt-cli.exe','muksmatt-bluray-nav.exe','tools/ffmpeg-2026-09-08/ffmpeg.exe','tools/ffmpeg-2026-09-08/ffprobe.exe','tools/ffmpeg-2026-09-08/libdvdcss-2.dll','tools/mediainfo-26.05/MediaInfo.exe','WINDOWS-THIRD-PARTY-LOCK.json','WINDOWS-MEDIA-DEPENDENCIES.json','README-WINDOWS.txt','SHA256SUMS.txt')) {
    if (-not (Test-Path (Join-Path $verifyRoot $item))) {
        throw "Incomplete Windows parity distribution: $item"
    }
}
foreach ($line in (Get-Content (Join-Path $verifyRoot 'SHA256SUMS.txt'))) {
    if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { throw "Malformed ZIP SHA256: $line" }
    $want = $Matches[1]
    $file = Join-Path $verifyRoot ($Matches[2].Replace('/', '\'))
    if (-not (Test-Path $file)) { throw "ZIP entry missing: $file" }
    $got = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
    if ($got -ne $want) { throw "Invalid ZIP content SHA256: $file" }
}
$zipSHA = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLowerInvariant()
"sha256 $zipSHA  muKsMaTT-0.0.3-Windows-amd64-FULL-PARITY-TEST.zip" | Set-Content -Path (Join-Path $dist 'WINDOWS-ZIP-SHA256.txt') -Encoding ascii
Write-Host "PASS: complete portable offline Windows test ZIP; SHA256 $zipSHA"
