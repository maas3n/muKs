#!/usr/bin/env python3
"""Inventory (never modify) the exact bundled runtime of Linux muKsMaTT v0.0.3.

This creates machine-readable per-file SHA256 and tool-probe manifests for a
Windows parity port. It deliberately does not assume that copying upstream
tool names or version strings provides feature or ABI parity.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

PAT = re.compile(
    r"ffmpeg|ffprobe|mediainfo|dvd|bluray|aacs|bdplus|udf|mkv|iso|"
    r"makemkv|libav|curl|openssl|zlib|iconv|vpx|x264|x265|hevc|"
    r"subtitle|ass|fontconfig|freetype|libxml|libcrypto|libssl",
    re.I
)
VERSION_CALLS = {
    "ffmpeg": ["-version"],
    "ffprobe": ["-version"],
    "mediainfo": ["--Version"],
    "mkvmerge": ["--version"],
    "mkvextract": ["--version"],
    "muksmatt-bluray-nav": ["--version"],
}
BANNED = ("/../",)

def hash_file(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def cmd(argv, timeout=15):
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
        return {"args": argv[1:], "returncode": p.returncode,
                "output": (p.stdout + "\n" + p.stderr)[:40000]}
    except (OSError, subprocess.TimeoutExpired) as ex:
        return {"args": argv[1:], "error": str(ex)}

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--payload", type=Path, required=True)
    a.add_argument("--source", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    args = a.parse_args()
    payload, source, out = args.payload.resolve(), args.source.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not (payload / "ffmpeg").is_file() or not (payload / "ffprobe").is_file():
        raise SystemExit("Verified Linux standalone payload lacks ffmpeg/ffprobe")
    rows, tools, versions = [], [], {}
    for p in sorted(payload.rglob("*")):
        if not (p.is_file() or p.is_symlink()):
            continue
        rel = p.relative_to(payload).as_posix()
        if p.is_symlink():
            row = {"path": rel, "kind": "symlink", "target": os.readlink(p)}
        else:
            with p.open("rb") as f:
                magic = f.read(4)
            kind = "ELF" if magic == b"\x7fELF" else "other"
            row = {"path": rel, "kind": kind, "size": p.stat().st_size,
                   "sha256": hash_file(p), "executable": os.access(p, os.X_OK)}
        rows.append(row)
        if PAT.search(rel) or row.get("kind") == "ELF":
            tools.append(row)
        if p.name in VERSION_CALLS and p.is_file() and os.access(p, os.X_OK):
            versions[rel] = cmd([str(p), *VERSION_CALLS[p.name]])

    ffmpeg = payload / "ffmpeg"
    if not any(k.split("/")[-1] == "ffmpeg" for k in versions):
        versions["ffmpeg"] = cmd([str(ffmpeg), "-version"])
    feature_checks = {
        "ffmpeg_build_configuration": cmd([str(ffmpeg), "-buildconf"]),
        "ffmpeg_demuxers": cmd([str(ffmpeg), "-demuxers"]),
        "ffmpeg_muxers": cmd([str(ffmpeg), "-muxers"]),
        "ffmpeg_protocols": cmd([str(ffmpeg), "-protocols"]),
        "ffmpeg_formats": cmd([str(ffmpeg), "-formats"]),
        "ffprobe_version": cmd([str(payload / "ffprobe"), "-version"]),
    }

    source_rows = []
    selected = []
    for p in sorted(source.rglob("*")):
        if not p.is_file() or p.stat().st_size > 1_000_000:
            continue
        rel = p.relative_to(source).as_posix()
        if re.search(r"\.(go|py|sh|ps1|md|yml|yaml|txt|json|c|h)$", p.name, re.I):
            try:
                lines = p.read_text(errors="replace").splitlines()
            except OSError:
                continue
            if PAT.search(rel) or re.search(r"windows|tool|packag|vendor|dependen", rel, re.I):
                selected.append(rel)
            for idx, line in enumerate(lines, 1):
                if re.search(r"(?i)(windows|tool|download|checksum|sha256|version|libbluray|ffmpeg|mediainfo|dvdvideo)", line):
                    if PAT.search(line) and (re.search(r"(?i)(version|download|checksum|sha256|https?|libbluray|ffmpeg|mediainfo|dvdvideo|tool)", line)):
                        source_rows.append({"file": rel, "line": idx, "text": line.strip()[:400]})

    payload_info = {
        "source_release": "muKsMaTT v0.0.3 (SHA256-verified official release)",
        "file_count": len(rows),
        "all_payload_files": rows,
        "potential_tools_and_native_libraries": tools,
        "runtime_versions": versions,
        "feature_checks": feature_checks,
        "source_tool_references": source_rows,
        "selected_source_files": selected,
    }
    (out / "linux-v0.0.3-runtime-manifest.json").write_text(
        json.dumps(payload_info, indent=2, sort_keys=True) + "\n")
    (out / "linux-v0.0.3-tool-files.txt").write_text(
        "".join(f"{r['path']}  {r.get('sha256', 'link:' + r.get('target', ''))}\n" for r in tools))
    (out / "linux-v0.0.3-source-dependency-references.txt").write_text(
        "".join(f"{r['file']}:{r['line']} {r['text']}\n" for r in source_rows))
    print("LINUX_REPORTED_BUNDLE_FILES", len(rows), flush=True)
    print("THIRD_PARTY_OR_NATIVE_RELATED_FILES", len(tools), flush=True)
    print("LINUX VERSION PROBES:", flush=True)
    for name, probe in versions.items():
        print(f"  {name}: {probe.get('output', probe.get('error', ''))[:600]!r}", flush=True)
    print("FFMPEG DVDVIDEO DEMUXER:",
          "dvdvideo" in feature_checks["ffmpeg_demuxers"].get("output", "").lower(), flush=True)
    print("MATCHING TOOL/LIBRARY PATHS:", flush=True)
    for row in tools[:250]:
        print("  ", row["path"], row.get("size", ""), flush=True)
    print("Source tool/dependency references:", len(source_rows), flush=True)
    print("Dependency manifest successfully generated; no application files modified", flush=True)

if __name__ == "__main__":
    main()
