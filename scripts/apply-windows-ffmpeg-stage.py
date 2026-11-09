#!/usr/bin/env python3
"""FFmpeg-only Windows DVD smoke-stage, NOT a full platform port.

Apply an intentionally minimal Windows-only offline-tool resolver to the exact
SHA-256 verified Linux v0.0.3 source. All shared and Linux .go files stay
untouched. Missing MediaInfo deliberately produces an explicit error rather
than downloading it; Blu-ray/optical media parity is NOT claimed.
"""
import hashlib
import sys
from pathlib import Path

EXPECTED_WINDOWS_FILE_SHA = "246fd6190bef370772227c71d6da555a8b6b9d11378b8ee31b20e7ceca690b98"
SIGNATURE = "func ensureTools(ctx context.Context, needMediaInfo bool) (toolPaths, error) {\n"
NEXT = "\nfunc installFFmpeg(ctx context.Context, dst string) error {"
PATCH = """func ensureTools(ctx context.Context, needMediaInfo bool) (toolPaths, error) {
    exe, err := os.Executable()
    if err != nil { return toolPaths{}, fmt.Errorf("locate Windows executable: %w", err) }
    root := filepath.Dir(exe)
    ffDir := filepath.Join(root, "tools", "ffmpeg-2026-09-08")
    miDir := filepath.Join(root, "tools", "mediainfo-"+mediaInfoVersion)
    tools := toolPaths{
        ffmpeg: filepath.Join(ffDir, "ffmpeg.exe"),
        ffprobe: filepath.Join(ffDir, "ffprobe.exe"),
        mediainfo: filepath.Join(miDir, "MediaInfo.exe"),
    }
    // OFFLINE FFmpeg-stage test. No first-launch media-tool downloads.
    // The complete Linux-equivalent third-party runtime is not yet bundled.
    for _, p := range []string{tools.ffmpeg, tools.ffprobe} {
        if !fileExists(p) { return toolPaths{}, fmt.Errorf("missing bundled Windows media tool: %s", p) }
    }
    if needMediaInfo && !fileExists(tools.mediainfo) {
        return toolPaths{}, fmt.Errorf("MediaInfo %s is not bundled in this FFmpeg-only test package: %s", mediaInfoVersion, tools.mediainfo)
    }
    out, err := runHidden(ctx, tools.ffmpeg, "-version")
    if err != nil { return toolPaths{}, fmt.Errorf("bundled FFmpeg failed: %w", err) }
    if !strings.Contains(string(out), "N-126479-g08cd8df29d") {
        return toolPaths{}, errors.New("bundled FFmpeg does not match Linux v0.0.3 upstream revision")
    }
    fp, err := runHidden(ctx, tools.ffprobe, "-version")
    if err != nil { return toolPaths{}, fmt.Errorf("bundled FFprobe failed: %w", err) }
    if !strings.Contains(string(fp), "N-126479-g08cd8df29d") {
        return toolPaths{}, errors.New("bundled FFprobe does not match Linux v0.0.3 upstream revision")
    }
    if err := checkDVDDemuxer(ctx, tools.ffmpeg); err != nil { return toolPaths{}, err }
    return tools, nil
}
"""
def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply-windows-ffmpeg-stage.py EXACT_V0.0.3_SOURCE_ROOT")
    root = Path(sys.argv[1]).resolve(strict=True)
    file = root / "src/app_windows_3.go"
    if not file.is_file():
        raise SystemExit("Wrong muKsMaTT source layout")
    actual = hashlib.sha256(file.read_bytes()).hexdigest()
    if actual != EXPECTED_WINDOWS_FILE_SHA:
        raise SystemExit("Original v0.0.3 Windows source hash mismatch: " + actual)
    text = file.read_text()
    if text.count(SIGNATURE) != 1 or text.count(NEXT) != 1:
        raise SystemExit("Original Windows ensureTools function is different; refuse patch")
    start = text.index(SIGNATURE)
    end = text.index(NEXT,start)
    if "installFFmpeg(ctx, ffDir)" not in text[start:end] or "installMediaInfo(ctx, miDir)" not in text[start:end]:
        raise SystemExit("Original download logic has unexpected changes")
    if not text.startswith("//go:build windows\n"):
        raise SystemExit("Refusing patch to non-Windows file")
    file.write_text(text[:start] + PATCH + text[end:])
    print("Applied FFmpeg-only OFFLINE Windows test resolver; all Linux source and shared engines unchanged")
if __name__ == "__main__":
    main()
