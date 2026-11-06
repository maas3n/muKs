#!/usr/bin/env python3
"""Fail-closed Windows-only patch atop exact SHA-256-verified v0.0.3 source.

Never modify Linux source, shared processing, DVD/Blu-ray engines or CLI syntax.
Windows media-tool resolution switches from app-data downloads to the fully
bundled verified files next to the application. The previous download helper
definitions remain untouched but are unreachable from ensureTools().
"""
import hashlib
import shutil
import sys
from pathlib import Path

VERSION_SHA = "246fd6190bef370772227c71d6da555a8b6b9d11378b8ee31b20e7ceca690b98"
FUNC_SIGNATURE = "func ensureTools(ctx context.Context, needMediaInfo bool) (toolPaths, error) {\n"
NEXT_FUNC = "\nfunc installFFmpeg(ctx context.Context, dst string) error {"
IMPLEMENTATION = """func ensureTools(ctx context.Context, needMediaInfo bool) (toolPaths, error) {
    exe, err := os.Executable()
    if err != nil {
        return toolPaths{}, fmt.Errorf("resolve muKsMaTT Windows executable: %w", err)
    }
    exeDir := filepath.Dir(exe)
    tools := bundledWindowsToolPaths(exeDir)
    if err := validateBundledWindowsToolFiles(exeDir, tools); err != nil {
        return toolPaths{}, err
    }
    // Match the exact upstream Linux FFmpeg commit; reject newer or older
    // system versions and refuse first-run downloads or PATH fallbacks.
    out, err := runHidden(ctx, tools.ffmpeg, "-version")
    if err != nil {
        return toolPaths{}, fmt.Errorf("cannot run bundled Windows FFmpeg: %w", err)
    }
    if !strings.Contains(string(out), "N-126479-g08cd8df29d") {
        return toolPaths{}, errors.New("bundled FFmpeg differs from Linux v0.0.3's pinned upstream commit N-126479-g08cd8df29d")
    }
    probeVersion, err := runHidden(ctx, tools.ffprobe, "-version")
    if err != nil {
        return toolPaths{}, fmt.Errorf("cannot run bundled Windows FFprobe: %w", err)
    }
    if !strings.Contains(string(probeVersion), "N-126479-g08cd8df29d") {
        return toolPaths{}, errors.New("bundled FFprobe does not match Linux v0.0.3")
    }
    if err := checkDVDDemuxer(ctx, tools.ffmpeg); err != nil {
        return toolPaths{}, fmt.Errorf("bundled FFmpeg lacks the exact DVD-Video capability required on Linux: %w", err)
    }
    if needMediaInfo {
        mediaVersion, err := runHidden(ctx, tools.mediainfo, "--Version")
        if err != nil {
            return toolPaths{}, fmt.Errorf("cannot run bundled Windows MediaInfo: %w", err)
        }
        if !strings.Contains(string(mediaVersion), "26.05") {
            return toolPaths{}, errors.New("bundled MediaInfo must match Linux v0.0.3 MediaInfoLib 26.05")
        }
    }
    return tools, nil
}
"""

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-windows-parity.py EXACT_V0.0.3_SOURCE_ROOT")
    root = Path(sys.argv[1]).resolve(strict=True)
    source = root / "src"
    src = source / "app_windows_3.go"
    if sha(src) != VERSION_SHA:
        raise RuntimeError("Refusing Windows patch: original v0.0.3 Windows tool resolver SHA256 does not match")
    original = src.read_text()
    if original.count(FUNC_SIGNATURE) != 1 or original.count(NEXT_FUNC) != 1:
        raise RuntimeError("Refusing Windows patch: original ensureTools boundaries changed")
    start = original.index(FUNC_SIGNATURE)
    end = original.index(NEXT_FUNC, start)
    prior = original[start:end]
    if "installFFmpeg(ctx, ffDir)" not in prior or "installMediaInfo(ctx, miDir)" not in prior:
        raise RuntimeError("Original Windows tool-download logic differs from expected")
    addition = source / "windows_bundled_tools.go"
    test = source / "windows_bundled_tools_test.go"
    if addition.exists() or test.exists():
        raise RuntimeError("Refusing to replace existing Windows bundled files")
    base = Path(__file__).resolve().parents[1] / "patches" / "windows-parity"
    for file in [base / "windows_bundled_tools.go", base / "windows_bundled_tools_test.go"]:
        if not file.is_file() or not file.read_text().startswith("//go:build windows"):
            raise RuntimeError("Missing Windows-specific helper or tests")
    # Only an existing Windows-tagged source file and two NEW Windows-tagged
    # files are changed. All source files used to build Linux stay identical.
    src.write_text(original[:start] + IMPLEMENTATION + original[end:])
    shutil.copy2(base / addition.name, addition)
    shutil.copy2(base / test.name, test)
    assert src.read_text().startswith("//go:build windows\n")
    print("PASS: patched only app_windows_3.go and added Windows-only bundled-tool resolver and tests")
    print("No shared media engine, Linux source, Windows CLI, or GUI tabs altered")

if __name__ == "__main__":
    main()
