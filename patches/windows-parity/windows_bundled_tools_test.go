//go:build windows

package main

import (
    "os"
    "path/filepath"
    "strings"
    "testing"
)

func TestWindowsBundledRuntimePaths(t *testing.T) {
    root := filepath.Join(t.TempDir(), "muKsMaTT")
    paths := bundledWindowsToolPaths(root)
    mustEqual := map[string]string{
        "FFmpeg": paths.ffmpeg,
        "FFprobe": paths.ffprobe,
        "MediaInfo": paths.mediainfo,
    }
    for name, path := range mustEqual {
        if !strings.HasPrefix(strings.ToLower(path), strings.ToLower(root)+string(os.PathSeparator)) {
            t.Fatalf("%s unexpectedly searches outside portable bundle: %q", name, path)
        }
    }
    if filepath.Base(paths.ffmpeg) != "ffmpeg.exe" ||
        filepath.Base(paths.ffprobe) != "ffprobe.exe" ||
        filepath.Base(paths.mediainfo) != "MediaInfo.exe" {
        t.Fatalf("unexpected bundled media tools: %+v", paths)
    }
}

func TestWindowsBundledRuntimeFailsClosedOnMissingDependencies(t *testing.T) {
    root := t.TempDir()
    tools := bundledWindowsToolPaths(root)
    if err := validateBundledWindowsToolFiles(root, tools); err == nil {
        t.Fatal("empty portable distribution must fail instead of downloading tools")
    }
    expected := []string{
        tools.ffmpeg,
        tools.ffprobe,
        tools.mediainfo,
        filepath.Join(filepath.Dir(tools.ffmpeg), "libdvdcss-2.dll"),
        filepath.Join(root, "muksmatt-bluray-nav.exe"),
        filepath.Join(root, "libbluray-4.dll"),
        filepath.Join(root, "libaacs-0.dll"),
        filepath.Join(root, "libbdplus-0.dll"),
    }
    for _, filename := range expected {
        if err := os.MkdirAll(filepath.Dir(filename), 0755); err != nil {
            t.Fatal(err)
        }
        if err := os.WriteFile(filename, []byte("present"), 0644); err != nil {
            t.Fatal(err)
        }
    }
    if err := validateBundledWindowsToolFiles(root, tools); err != nil {
        t.Fatalf("complete portable bundle should resolve: %v", err)
    }
    if err := os.Remove(filepath.Join(root, "libaacs-0.dll")); err != nil {
        t.Fatal(err)
    }
    if err := validateBundledWindowsToolFiles(root, tools); err == nil {
        t.Fatal("removing an essential Blu-ray DLL must fail closed")
    }
}
