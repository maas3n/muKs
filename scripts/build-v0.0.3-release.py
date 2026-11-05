#!/usr/bin/env python3
"""Package muKsMaTT 0.0.3 from the merged, tested PR#2 source.

Use the ORIGINAL v.0.0.2 Linux distribution files for every non-application
binary/library. Replace ONLY the newly compiled GUI and CLI, update Debian
version metadata and README, and export the merged source. Fail closed on any
unrelated changes; never rebuild FFmpeg, MediaInfo or the DVD/Blu-ray engine.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

VERSION = "0.0.3"
PRIOR = "0.0.2"
PREFIX = "muKsMaTT"
PRIOR_HASH = {
    f"{PREFIX}-{PRIOR}-Linux-amd64.deb": "8275006216649c1eb163f223ef696f5b1914d6e25f361f992cf1991fb48c0e23",
    f"{PREFIX}-{PRIOR}-Linux-amd64.tar.gz": "8858ac82463132b0c147467ee3589646b7d42ea08722e371aba020f4b9e380aa",
    f"{PREFIX}-{PRIOR}-Linux-Library-Sources.tar.gz": "5d6048d9d4ba1bc3289b897887e818ef369597d25c0a0c6f998db38b50d29ec5",
}
STANDALONE_NAME = f"{PREFIX}-{VERSION}-Linux-amd64Standalone"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def execute(*args):
    subprocess.run(args, check=True)


def untar(name, dest):
    with tarfile.open(name, "r:gz") as archive:
        archive.extractall(dest, filter="data")


def tar_dir(dest_file, base, entry):
    with tarfile.open(dest_file, "w:gz") as archive:
        archive.add(base / entry, arcname=entry)


def ensure_same_tree(original, modified, approved):
    original = Path(original)
    modified = Path(modified)
    first = {x.relative_to(original) for x in original.rglob("*") if x.is_file() or x.is_symlink()}
    second = {x.relative_to(modified) for x in modified.rglob("*") if x.is_file() or x.is_symlink()}
    if first != second:
        raise RuntimeError(f"Unexpected added/deleted package files: {first ^ second}")
    for rel in sorted(first - approved):
        a, b = original / rel, modified / rel
        if a.is_symlink() or b.is_symlink():
            if not (a.is_symlink() and b.is_symlink() and os.readlink(a) == os.readlink(b)):
                raise RuntimeError(f"Non-application symlink modified: {rel}")
        elif sha(a) != sha(b):
            raise RuntimeError(f"Non-application binary or library modified: {rel}")


def verify_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty file: {path}")


def main():
    ap = argparse.ArgumentParser()
    for arg in ["prior-assets", "patched-source", "gui", "cli", "standalone", "out"]:
        ap.add_argument("--" + arg, type=Path, required=True)
    args = vars(ap.parse_args())
    prior, source, gui, cli, standalone, out = (args[k].resolve() for k in
        ["prior_assets", "patched_source", "gui", "cli", "standalone", "out"])
    out.mkdir(parents=True, exist_ok=True)

    for name, expected in PRIOR_HASH.items():
        path = prior / name
        verify_file(path)
        if sha(path) != expected:
            raise RuntimeError(f"Prior v.0.0.2 asset checksum changed: {name}")
        print("Verified unchanged v.0.0.2 package:", name, flush=True)

    for item in [gui, cli, standalone, source / "src/desktop_cli_dvd_demux.go",
                 source / "src/desktop_cli_dvd_demux_test.go"]:
        verify_file(item)

    with tempfile.TemporaryDirectory(prefix="muksmatt-003-") as temp:
        work = Path(temp)
        # The new source archive contains the exact source used for the new
        # GUI and CLI builds, including the existing v.0.0.2 UI fix.
        src_dir = work / "source"
        src_dir.mkdir()
        source_name = f"{PREFIX}-{VERSION}-Source"
        shutil.copytree(source, src_dir / source_name, symlinks=True)
        tar_dir(out / (source_name + ".tar.gz"), src_dir, source_name)

        # Debian package: update GUI and CLI binaries and Debian version
        # ONLY; retain all FFmpeg, FFprobe, MediaInfo, libdvdcss, navigation
        # binaries, installed shell launchers, notices and dependencies.
        deb_original = work / "deb-original"
        deb_new = work / "deb-new"
        execute("dpkg-deb", "--raw-extract",
                str(prior / f"{PREFIX}-{PRIOR}-Linux-amd64.deb"), str(deb_original))
        shutil.copytree(deb_original, deb_new, symlinks=True)
        gui_rel = Path("usr/lib/muksmatt/app/muksmatt-bin")
        cli_rel = Path("usr/lib/muksmatt/app/muksmatt-cli-bin")
        ctl_rel = Path("DEBIAN/control")
        for rel, binary in [(gui_rel, gui), (cli_rel, cli)]:
            verify_file(deb_new / rel)
            shutil.copy2(binary, deb_new / rel)
        ctl = (deb_new / ctl_rel).read_text()
        previous_line = f"Version: {PRIOR}\n"
        if ctl.count(previous_line) != 1:
            raise RuntimeError("Original Debian package version does not match v.0.0.2")
        (deb_new / ctl_rel).write_text(ctl.replace(previous_line, f"Version: {VERSION}\n"))
        ensure_same_tree(deb_original, deb_new, {gui_rel, cli_rel, ctl_rel})
        deb_out = out / f"{PREFIX}-{VERSION}-Linux-amd64.deb"
        execute("dpkg-deb", "--build", "--root-owner-group", str(deb_new), str(deb_out))
        actual_version = subprocess.check_output(
            ["dpkg-deb", "--field", str(deb_out), "Version"], text=True).strip()
        if actual_version != VERSION:
            raise RuntimeError(f"Bad Debian version: {actual_version}")
        deb_check = work / "deb-check"
        execute("dpkg-deb", "--raw-extract", str(deb_out), str(deb_check))
        ensure_same_tree(deb_original, deb_check, {gui_rel, cli_rel, ctl_rel})
        if sha(deb_check / gui_rel) != sha(gui) or sha(deb_check / cli_rel) != sha(cli):
            raise RuntimeError("Debian GUI/CLI binaries differ from compiled v0.0.3")
        print("Debian verified: GUI and CLI updated, ALL media binaries unchanged", flush=True)

        # Portable Linux: keep existing file layout and libdvdcss runtime.
        portable = work / "portable"
        portable.mkdir()
        untar(prior / f"{PREFIX}-{PRIOR}-Linux-amd64.tar.gz", portable)
        previous_dir = portable / f"{PREFIX}-{PRIOR}-Linux-amd64"
        if not previous_dir.is_dir():
            raise RuntimeError("Unexpected portable release root")
        old_copy = work / "portable-original"
        shutil.copytree(previous_dir, old_copy, symlinks=True)
        portable_gui = Path("muksmatt")
        portable_cli = Path("muksmatt-cli")
        portable_readme = Path("README-LINUX.txt")
        for rel, binary in [(portable_gui, gui), (portable_cli, cli)]:
            verify_file(previous_dir / rel)
            shutil.copy2(binary, previous_dir / rel)
        if (previous_dir / portable_readme).is_file():
            readme = (previous_dir / portable_readme).read_text()
            if PRIOR not in readme:
                raise RuntimeError("Portable README missing old version")
            (previous_dir / portable_readme).write_text(readme.replace(PRIOR, VERSION))
        ensure_same_tree(old_copy, previous_dir,
                         {portable_gui, portable_cli, portable_readme})
        portable_dir_name = f"{PREFIX}-{VERSION}-Linux-amd64"
        (portable / f"{PREFIX}-{PRIOR}-Linux-amd64").rename(portable / portable_dir_name)
        portable_out = out / (portable_dir_name + ".tar.gz")
        tar_dir(portable_out, portable, portable_dir_name)
        with tarfile.open(portable_out, "r:gz") as archive:
            for rel, binary in [(portable_gui, gui), (portable_cli, cli)]:
                member = archive.extractfile(str(Path(portable_dir_name) / rel))
                if member is None or hashlib.sha256(member.read()).hexdigest() != sha(binary):
                    raise RuntimeError(f"Portable {rel} binary is not the compiled v0.0.3 version")
        print("Portable verified: both GUI and CLI updated; runtime unchanged", flush=True)

        # Bundled third-party library source code did not change.
        lib_out = out / f"{PREFIX}-{VERSION}-Linux-Library-Sources.tar.gz"
        shutil.copy2(prior / f"{PREFIX}-{PRIOR}-Linux-Library-Sources.tar.gz", lib_out)
        if sha(lib_out) != PRIOR_HASH[f"{PREFIX}-{PRIOR}-Linux-Library-Sources.tar.gz"]:
            raise RuntimeError("Bundled third-party library sources changed")
        shutil.copy2(standalone, out / STANDALONE_NAME)
        if sha(out / STANDALONE_NAME) != sha(standalone):
            raise RuntimeError("v0.0.3 standalone copy differs from tested build")

    distribution_files = [
        f"{PREFIX}-{VERSION}-Linux-amd64.deb",
        f"{PREFIX}-{VERSION}-Linux-amd64.tar.gz",
        f"{PREFIX}-{VERSION}-Source.tar.gz",
        f"{PREFIX}-{VERSION}-Linux-Library-Sources.tar.gz",
        STANDALONE_NAME,
    ]
    sums = out / "SHA256SUMS.txt"
    sums.write_text("".join(f"{sha(out / name)}  {name}\n" for name in distribution_files))

    # Include every new release package and its checksums in the dev ZIP.
    zip_name = f"{PREFIX}-{VERSION}-Linux-amd64-dev.zip"
    with zipfile.ZipFile(out / zip_name, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        for name in distribution_files + ["SHA256SUMS.txt"]:
            archive.write(out / name, arcname=name)
    with zipfile.ZipFile(out / zip_name) as archive:
        failure = archive.testzip()
        if failure is not None:
            raise RuntimeError(f"Development ZIP CRC failure: {failure}")
        if set(archive.namelist()) != set(distribution_files + ["SHA256SUMS.txt"]):
            raise RuntimeError("Incomplete development ZIP")
    sums.write_text("".join(f"{sha(out / name)}  {name}\n"
                            for name in distribution_files + [zip_name]))
    for name in distribution_files + [zip_name, "SHA256SUMS.txt"]:
        verify_file(out / name)
        print(f"Asset {name} size={ (out / name).stat().st_size} sha256={sha(out / name)}",
              flush=True)
    print("All 7 complete v0.0.3 Linux release assets built and verified", flush=True)


if __name__ == "__main__":
    main()
