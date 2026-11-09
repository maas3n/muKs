# Windows parity: FFmpeg/DVD smoke-test stage (INCOMPLETE)

**Scope:** an isolated native Windows GUI + CLI smoke test of user-supplied
FFmpeg/FFprobe/FFplay and seven matching DLLs. This is **not** a complete
Windows muKsMaTT port or an official release.

## Verified Linux reference
- Official Linux v0.0.3 source tarball SHA-256:
  `d36d9e4128d0a9432d3da4916c5de7777208f0faf578d83b7f6c24055b5cbe10`.
- Linux standalone FFmpeg SHA-256:
  `d6454810f94fb770722f804cdb1818c3933f6167d01f4d36ddf3450785f43f25`.
- Linux standalone FFprobe SHA-256:
  `46f0ff246fe0b6bca755938b287bea52ee4a7199af5e63ea5bb7ee683297fff6`.
- Earlier Linux developer Debian package includes **byte-identical** FFmpeg,
  FFprobe and MediaInfo binaries; these were verified against the official
  v0.0.3 standalone inventory. The exact Linux binaries were then executed
  on a copyright-free authored DVD from GitHub Actions run `42216141906`.
- Linux reference stream analysis: MPEG-2 video 720x576, AC-3 mono audio,
  DVD subtitle, **2 chapters**.
- Exact Linux DVD title 1 elementary output hashes:
  - Video: `927344eb8cbb28ad24e490a7a30f55b0cabff9c9c3e3b54688fdaa4c916b32df`
  - Audio: `f721ef84e2ee658eb6922e1b53db97f2191c715bc33ebd390c92b9630a924a3f`

## Candidate Windows FFmpeg build
- User-supplied Windows amd64 FFmpeg binaries; exact reported source revision
  `N-126479-g08cd8df29d-20260908`.
- Each of the 10 files is pinned by SHA-256 in
  `patches/windows-parity/user-uploaded-ffmpeg-sha256.json`.
- Embedded build options include `--enable-libdvdread`,
  `--enable-libdvdnav`, `--enable-libbluray`, and `--enable-gpl`.
- Unlike Linux's `--enable-openssl`, Windows uses `--enable-schannel`.
  This is documented as an important platform build difference.
- Publisher archive SHA-256 remains **unavailable**. User-file hashes
  prove file identity, not original publisher authenticity.
- Static imports do not show unresolved third-party direct dependencies,
  but native Windows loading/dlopen and media operations remain untested.

## Repeatable source patch
The script `scripts/apply-windows-ffmpeg-stage.py` accepts the verified
**v0.0.3 source tree** and changes ONLY `src/app_windows_3.go`'s
Windows-only `ensureTools()`. It refuses unrecognized original source.
Windows first-run FFmpeg and MediaInfo downloads are not used. The missing
MediaInfo program is reported as a **missing dependency**, not replaced
or silently downloaded.

The working Linux engine, Linux CLI, shared media code, native Windows tabs,
and underlying DVD/Blu-ray processing implementation are unchanged.

## End-to-end test required on Windows
A private local FFmpeg/DVD smoke-test ZIP has been created for the owner in
this ChatGPT conversation. It contains the user-provided binary stack,
locally cross-compiled Windows GUI/CLI, an authored DVD, exact Linux golden
outputs, and a PowerShell runner which checks hashes, starts FFmpeg and
FFprobe, tests the DVDVideo demuxer, runs actual DVD stream copies and
muKsMaTT DVD `scan`, `metadata`, `remux`, `demux`, and
`advanced demux` commands.

**These Windows tests have not been executed by a Windows host yet.**
The test runner saves `WINDOWS_TEST_RESULTS.zip` for inspection. No results
are uploaded automatically.

## Remaining before full parity
- Source-approved MediaInfo 26.05 native Windows build and DLL closure
- Exact libbluray 1.3.4, libaacs 0.11.1, libbdplus 0.2.0,
  libdvdcss 1.6.0, and libudfread 1.1.2 capabilities
- Native Blu-ray helper and optical drive / ISO functionality
- DVD subtitles and chapters equivalence; Blu-ray playlist equivalence
- GUI tab-by-tab and CLI flag-by-flag behavior comparison
- Protected DVD, physical drive, ISO media and real-disc tests
- Fully offline ZIP test with all dependencies and applicable notices
- Explicit owner approval before any merge or release

**Never claim parity solely because the Windows program compiles.**
