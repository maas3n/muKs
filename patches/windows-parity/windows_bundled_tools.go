//go:build windows

package main

import (
    "fmt"
    "os"
    "path/filepath"
)

// bundledWindowsToolPaths resolves ONLY files shipped with this portable
// Windows distribution. The Linux application and its tool selection are
// completely unaffected.
func bundledWindowsToolPaths(exeDir string) toolPaths {
    ffDir := filepath.Join(exeDir, "tools", "ffmpeg-2026-09-08")
    miDir := filepath.Join(exeDir, "tools", "mediainfo-"+mediaInfoVersion)
    return toolPaths{
        ffmpeg:    filepath.Join(ffDir, "ffmpeg.exe"),
        ffprobe:   filepath.Join(ffDir, "ffprobe.exe"),
        mediainfo: filepath.Join(miDir, "MediaInfo.exe"),
    }
}

// Fail closed if any Windows counterpart of the Linux media runtime is absent.
// No silently downloaded or system-PATH substitutions, including for DVD CSS
// or Blu-ray navigation. Versions and FFmpeg capabilities are separately
// validated by the Windows release-parity CI.
func validateBundledWindowsToolFiles(exeDir string, tools toolPaths) error {
    required := []string{
        tools.ffmpeg,
        tools.ffprobe,
        tools.mediainfo,
        filepath.Join(filepath.Dir(tools.ffmpeg), "libdvdcss-2.dll"),
        filepath.Join(exeDir, "muksmatt-bluray-nav.exe"),
        filepath.Join(exeDir, "libbluray-4.dll"),
        filepath.Join(exeDir, "libaacs-0.dll"),
        filepath.Join(exeDir, "libbdplus-0.dll"),
    }
    for _, path := range required {
        info, err := os.Stat(path)
        if err != nil || info.IsDir() || info.Size() == 0 {
            return fmt.Errorf("required bundled Windows media component missing or empty: %s (re-extract the complete muKsMaTT Windows ZIP)", path)
        }
    }
    return nil
}
