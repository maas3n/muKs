#!/usr/bin/env python3
"""Stage the EXACT pinned Linux-v0.0.3-equivalent Windows FFmpeg/MediaInfo.

This is a CI-time download with release-manifest/archive SHA256 validation.
It creates a self-contained OFFLINE runtime; application launch does NOT fetch
third-party tools, and no different or newer FFmpeg/MediaInfo is substituted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

FF_TAG = "autobuild-2026-09-08-23-15"
FF_REVISION = "N-126479-g08cd8df29d"
FF_ARCHIVE = "ffmpeg-N-126479-g08cd8df29d-win64-gpl-shared.zip"
FF_CHECKSUM_MANIFEST_SHA = "f64be162403094773397bfcc299a4a059507028afa7563591fd05c17d56b3214"
MI_VERSION = "26.05"
MI_ARCHIVE = "MediaInfo_CLI_26.05_Windows_x64.zip"
MI_ARCHIVE_SHA = "f7f80620ce6d14f4995f0de6f98e3ef18ad29496db01899571152ee3311229f9"

def sha(path):
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(2 * 1024 * 1024), b""):
            hasher.update(part)
    return hasher.hexdigest()

def download(url, output, limit):
    if not url.lower().startswith("https://"):
        raise RuntimeError("Only pinned HTTPS upstream source downloads allowed")
    request = urllib.request.Request(url, headers={"User-Agent": "muKsMaTT-v0.0.3-Windows-Parity-CI"})
    with urllib.request.urlopen(request, timeout=70) as stream, output.open("wb") as f:
        if not stream.geturl().lower().startswith("https://"):
            raise RuntimeError("Refusing redirect to non-HTTPS content")
        content_length = stream.headers.get("content-length")
        if content_length and int(content_length) > limit:
            raise RuntimeError("Upstream archive exceeds maximum expected size")
        size = 0
        while True:
            chunk = stream.read(2 * 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise RuntimeError("Upstream download exceeded permitted size")
            f.write(chunk)
    print(f"Fetched verified upstream candidate {output.name}: {size} bytes", flush=True)

def verify(path, expected):
    result = sha(path)
    if result.lower() != expected.lower():
        raise RuntimeError(f"Refusing upstream asset due to SHA256 mismatch: {path.name} {result} != {expected}")
    return result

def zip_extract_checked(zippath, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zippath) as z:
        if z.testzip() is not None:
            raise RuntimeError(f"Corrupt upstream ZIP: {zippath.name}")
        if len(z.infolist()) > 10000:
            raise RuntimeError("Too many files in upstream ZIP")
        for item in z.infolist():
            raw = item.filename.replace("\\", "/")
            parts = Path(raw).parts
            if (raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or
                not parts or any(p == ".." for p in parts)):
                raise RuntimeError(f"Unsafe upstream ZIP path: {raw}")
            if item.file_size > 400 * 1024 * 1024:
                raise RuntimeError("Unexpected oversized archive member")
            target = dest.joinpath(*parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as reader, target.open("wb") as writer:
                shutil.copyfileobj(reader, writer, 2 * 1024 * 1024)

def only_file(root, name):
    files = list(root.rglob(name))
    if len(files) != 1:
        raise RuntimeError(f"Expected exactly one {name} in upstream ZIP; got {len(files)}")
    return files[0]

def execute(binary, *args):
    p = subprocess.run([str(binary), *args], capture_output=True, text=True, errors="replace",
                       timeout=35)
    out = p.stdout + "\n" + p.stderr
    if p.returncode != 0:
        raise RuntimeError(f"Bundled {binary.name} failed {args}: {out[:1500]}")
    return out

def validate_source_pins(app_source):
    s = app_source.read_text(encoding="utf-8")
    for constant, value in [
        ("ffmpegReleaseTag", FF_TAG),
        ("ffmpegAssetName", FF_ARCHIVE),
        ("ffmpegManifestSHA", FF_CHECKSUM_MANIFEST_SHA),
        ("mediaInfoVersion", MI_VERSION),
        ("mediaInfoAssetName", MI_ARCHIVE),
        ("mediaInfoSHA", MI_ARCHIVE_SHA),
    ]:
        pattern = r'(?m)^\s*' + re.escape(constant) + r'\s*=\s*"' + re.escape(value) + r'"\s*$'
        if not re.search(pattern, s):
            raise RuntimeError(f"Original v0.0.3 source does not pin expected {constant} = {value}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--dest", type=Path, required=True)
    args = ap.parse_args()
    source = args.source.resolve(strict=True)
    dest = args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    validate_source_pins(source / "src/app_windows.go")

    ff_base = "https://github.com/BtbN/FFmpeg-Builds/releases/download/" + FF_TAG
    mi_url = "https://mediaarea.net/download/binary/mediainfo/" + MI_VERSION + "/" + MI_ARCHIVE
    with tempfile.TemporaryDirectory(prefix="muksmatt-pin-") as td:
        w = Path(td)
        manifest = w / "ffmpeg-checksums.sha256"
        download(ff_base + "/checksums.sha256", manifest, 2 * 1024 * 1024)
        verify(manifest, FF_CHECKSUM_MANIFEST_SHA)
        candidates = {}
        for line in manifest.read_text(errors="replace").splitlines():
            fields = line.strip().split()
            if len(fields) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]):
                filename = fields[-1].lstrip("*")
                candidates[filename] = fields[0].lower()
        ff_expected = candidates.get(FF_ARCHIVE)
        if not ff_expected:
            raise RuntimeError("Verified BtbN release manifest omitted exact pinned FFmpeg build")

        ff_zip = w / FF_ARCHIVE
        mi_zip = w / MI_ARCHIVE
        download(ff_base + "/" + FF_ARCHIVE, ff_zip, 300 * 1024 * 1024)
        verify(ff_zip, ff_expected)
        download(mi_url, mi_zip, 60 * 1024 * 1024)
        verify(mi_zip, MI_ARCHIVE_SHA)
        ff_raw, mi_raw = w / "ffmpeg-extract", w / "mediainfo-extract"
        zip_extract_checked(ff_zip, ff_raw)
        zip_extract_checked(mi_zip, mi_raw)
        ff = only_file(ff_raw, "ffmpeg.exe")
        ffprobe = only_file(ff_raw, "ffprobe.exe")
        if ff.parent != ffprobe.parent:
            raise RuntimeError("Pinned FFmpeg archive separates its executables unexpectedly")
        mediainfo = only_file(mi_raw, "MediaInfo.exe")
        ff_dest = dest / "tools" / "ffmpeg-2026-09-08"
        mi_dest = dest / "tools" / ("mediainfo-" + MI_VERSION)
        ff_dest.mkdir(parents=True, exist_ok=True)
        mi_dest.mkdir(parents=True, exist_ok=True)
        for entry in ff.parent.iterdir():
            if entry.is_file():
                shutil.copy2(entry, ff_dest / entry.name)
        for entry in mediainfo.parent.iterdir():
            if entry.is_file():
                shutil.copy2(entry, mi_dest / entry.name)
        if not (ff_dest / "ffprobe.exe").is_file() or not (mi_dest / "MediaInfo.exe").is_file():
            raise RuntimeError("Incomplete FFmpeg or MediaInfo distribution")
        # Include accompanying legal notices when supplied by the upstream
        # archives. Original archive provenance and GPL variant are recorded.
        legal_dest = dest / "licenses" / "upstream"
        legal_dest.mkdir(parents=True, exist_ok=True)
        for label, raw_root in [("ffmpeg", ff_raw), ("mediainfo", mi_raw)]:
            matches = [p for p in raw_root.rglob("*")
                       if p.is_file() and p.name.lower() in
                       ("license", "license.txt", "copying", "copying.txt")]
            for i, p in enumerate(matches[:8]):
                shutil.copy2(p, legal_dest / (label + "-" + str(i) + "-" + p.name))

        ff_output = execute(ff_dest / "ffmpeg.exe", "-version")
        fp_output = execute(ff_dest / "ffprobe.exe", "-version")
        media_output = execute(mi_dest / "MediaInfo.exe", "--Version")
        dvd_output = execute(ff_dest / "ffmpeg.exe", "-hide_banner", "-demuxers")
        protocols = execute(ff_dest / "ffmpeg.exe", "-hide_banner", "-protocols")
        if FF_REVISION not in ff_output or FF_REVISION not in fp_output:
            raise RuntimeError("Windows FFmpeg/FFprobe revision differs from Linux v0.0.3")
        if MI_VERSION not in media_output:
            raise RuntimeError("Windows MediaInfo does not match Linux 26.05")
        if not re.search(r"(?m)^\s*D\s+dvdvideo\s", dvd_output):
            raise RuntimeError("Windows FFmpeg lacks Linux's dvdvideo demuxer")
        if not re.search(r"(?m)^\s+bluray\s*$", protocols):
            raise RuntimeError("Windows FFmpeg lacks Linux's Blu-ray protocol")

        lock = {
            "reference": "Linux v0.0.3 actual verified standalone",
            "ffmpeg_revision": FF_REVISION,
            "ffmpeg_release_tag": FF_TAG,
            "ffmpeg_windows_archive": FF_ARCHIVE,
            "ffmpeg_manifest_sha256": FF_CHECKSUM_MANIFEST_SHA,
            "ffmpeg_archive_sha256": ff_expected,
            "ffmpeg_exe_sha256": sha(ff_dest / "ffmpeg.exe"),
            "ffprobe_exe_sha256": sha(ff_dest / "ffprobe.exe"),
            "mediaInfoVersion": MI_VERSION,
            "mediainfo_archive_sha256": MI_ARCHIVE_SHA,
            "mediainfo_exe_sha256": sha(mi_dest / "MediaInfo.exe"),
            "dvdvideo_demuxer": True, "bluray_protocol": True,
            "download_policy": "CI time only, Windows runtime uses exclusively bundled files",
        }
        (dest / "WINDOWS-THIRD-PARTY-LOCK.json").write_text(
            json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("PASS: same FFmpeg upstream revision and MediaInfo version as Linux, DVDVideo and Blu-ray capability present", flush=True)
        print(json.dumps(lock, indent=2), flush=True)

if __name__ == "__main__":
    main()
