#!/usr/bin/env python3
"""Bundle exact-version Windows Blu-ray and DVD CSS runtime DLL closures.

All media libraries must originate in the pinned native Windows toolchain.
Do not copy Windows OS DLLs. Do not add BDInfo or substitute different media
engines. Package both the navigator's dependent DLLs and DVD CSS beside FFmpeg.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "cabinet.dll", "comctl32.dll",
    "comdlg32.dll", "crypt32.dll", "d2d1.dll", "dwmapi.dll",
    "gdi32.dll", "imm32.dll", "dwrite.dll", "usp10.dll",
    "msimg32.dll", "d3d11.dll", "d3dcompiler_47.dll", "shcore.dll",
    "propsys.dll", "uxtheme.dll", "iphlpapi.dll", "kernel32.dll",
    "msvcrt.dll", "ncrypt.dll", "netapi32.dll", "normaliz.dll",
    "ntdll.dll", "ole32.dll", "oleaut32.dll", "opengl32.dll",
    "psapi.dll", "rpcrt4.dll", "secur32.dll", "setupapi.dll",
    "shell32.dll", "shlwapi.dll", "ucrtbase.dll", "user32.dll",
    "userenv.dll", "version.dll", "winhttp.dll", "wininet.dll",
    "winmm.dll", "ws2_32.dll", "wsock32.dll",
}
REQUIRED = ("libaacs-0.dll", "libbdplus-0.dll", "libdvdcss-2.dll")
LICENSES = ("libbluray", "libaacs", "libbdplus", "libdvdcss")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()

def imported(path, objdump):
    p = subprocess.run([str(objdump), "-p", str(path)],
                       capture_output=True, text=True, check=True)
    return set(re.findall(r"^\s*DLL Name:\s*(\S+)\s*$",
                          p.stdout, re.IGNORECASE | re.MULTILINE))

def system_dll(name):
    low = name.casefold()
    return (low in SYSTEM_DLLS or low.startswith(("api-ms-win-", "ext-ms-win-"))
            or low.endswith(".drv"))

def copy_checked(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if sha(src) != sha(dest):
            raise RuntimeError(f"Refusing to overwrite different runtime DLL: {dest}")
        return
    shutil.copy2(src, dest)

def closure(roots, available, objdump):
    pending = list(roots)
    seen = set()
    files = {}
    while pending:
        file = pending.pop()
        low = file.name.casefold()
        if low in seen:
            continue
        seen.add(low)
        files[file.name] = file
        for dll in sorted(imported(file, objdump)):
            if system_dll(dll):
                continue
            match = available.get(dll.casefold())
            if match is None:
                raise RuntimeError(f"Unresolved native DLL imported by {file.name}: {dll}")
            pending.append(match)
    return files

def run():
    a = argparse.ArgumentParser()
    for field in ["helper", "mingw-bin", "objdump", "dest", "ffmpeg-dir"]:
        a.add_argument("--"+field, type=Path, required=True)
    args = a.parse_args()
    helper = args.helper.resolve(strict=True)
    bin_dir = getattr(args, "mingw_bin").resolve(strict=True)
    objdump = args.objdump.resolve(strict=True)
    stage = args.dest.resolve()
    ffmpeg = getattr(args, "ffmpeg_dir").resolve(strict=True)
    available = {p.name.casefold(): p for p in bin_dir.glob("*.dll")}
    bluray = [p for p in available.values()
              if re.fullmatch(r"libbluray-\d+\.dll", p.name, re.IGNORECASE)]
    if len(bluray) != 1:
        raise RuntimeError(f"Expected exactly one verified libbluray DLL (got {len(bluray)})")
    for name in REQUIRED:
        if name.casefold() not in available:
            raise RuntimeError(f"Matching Windows media dependency not available: {name}")
    primary = closure([helper, bluray[0],
                       available["libaacs-0.dll"], available["libbdplus-0.dll"]],
                      available, objdump)
    if bluray[0].name not in primary:
        raise RuntimeError("libbluray DLL not staged")
    css = closure([available["libdvdcss-2.dll"]], available, objdump)
    stage.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, src in sorted(primary.items()):
        dest = stage / name
        copy_checked(src, dest)
        manifest[name] = {"sha256": sha(dest), "bytes": dest.stat().st_size}
    for name, src in sorted(css.items()):
        # FFmpeg starts as a child process; Windows resolves its DLLs from the
        # executable's own folder, not necessarily from the GUI folder.
        copy_checked(src, ffmpeg / name)
        manifest["tools/ffmpeg-2026-09-08/"+name] = {
            "sha256": sha(ffmpeg / name), "bytes": (ffmpeg / name).stat().st_size}
    for library in LICENSES:
        options = [bin_dir.parent/"share"/"licenses"/library/"COPYING",
                   bin_dir.parent/"share"/"doc"/library/"COPYING"]
        original = next((f for f in options if f.is_file()), None)
        if original is None:
            raise RuntimeError(f"Missing distributable license for {library}")
        copy_checked(original, stage/"licenses"/library/"COPYING")
    obj = {"linux_compat_target": "muKsMaTT Linux v0.0.3",
           "libbluray_windows_dll": bluray[0].name,
           "windows_bundled_files": manifest,
           "dependency_sources": "MSYS2 package versions validated in CI",
           "notes": "No DVD/Blu-ray engine substitutions or BDInfo binaries"}
    (stage/"WINDOWS-MEDIA-DEPENDENCIES.json").write_text(
        json.dumps(obj, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print("Bundled native Windows Blu-ray DLL closure:",
          sorted(primary.keys()), flush=True)
    print("Bundled libdvdcss DLL closure beside FFmpeg:",
          sorted(css.keys()), flush=True)
    print("Total verified native dependency files:", len(manifest), flush=True)

if __name__ == "__main__":
    run()
