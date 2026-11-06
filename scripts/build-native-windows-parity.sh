#!/usr/bin/env bash
set -euo pipefail

# Linux v0.0.3 includes libbluray 1.3.4; modern MSYS2 provides 1.5.0.
# Install the exact upstream 1.3.4 from MSYS2's SIGNED historical archive.
# Do not silently substitute newer Blu-ray engines.
test "$GITHUB_REPOSITORY" = 'maas3n/muKs'
pkg='mingw-w64-x86_64-libbluray-1.3.4-1-any.pkg.tar.zst'
url="https://repo.msys2.org/mingw/mingw64/$pkg"
work="$(cygpath -u "$RUNNER_TEMP")/muksmatt-libbluray-pinned"
mkdir -p "$work"
cd "$work"

curl -fLSs --retry 4 --retry-delay 2 "$url" -o "$pkg"
curl -fLSs --retry 4 --retry-delay 2 "$url.sig" -o "$pkg.sig"
pacman-key --verify "$pkg.sig" "$pkg"
pacman --noconfirm -U "$pkg"

pkgver() { pacman -Q "$1" | awk '{print $2}'; }
test "$(pkgver mingw-w64-x86_64-libbluray)" = '1.3.4-1'
test "$(pkg-config --modversion libbluray)" = '1.3.4'
test "$(pkgver mingw-w64-x86_64-libaacs | cut -d- -f1)" = '0.11.1'
test "$(pkgver mingw-w64-x86_64-libbdplus | cut -d- -f1)" = '0.2.0'
test "$(pkgver mingw-w64-x86_64-libdvdcss | cut -d- -f1)" = '1.6.0'

src="$(cygpath -u "$PARITY_SOURCE")"
stage="$(cygpath -u "$PARITY_STAGE")"
test -f "$src/tools/bluray/bluray_nav.c"
cc -O2 -Wall -Wextra -Werror \
  -o "$stage/muksmatt-bluray-nav.exe" "$src/tools/bluray/bluray_nav.c" \
  $(pkg-config --cflags --libs libbluray)
test "$("$stage/muksmatt-bluray-nav.exe" --version)" = 'MUKSMATT_BD_NAV_1'
objdump -p "$stage/muksmatt-bluray-nav.exe" | grep -i 'DLL Name:.*libbluray'
sha256sum "$pkg" > "$stage/WINDOWS-LIBBLURAY-PACKAGE-SHA256.txt"

{
  echo "LINUX reference muKsMaTT v0.0.3 native media stack"
  pacman -Q mingw-w64-x86_64-libbluray
  pacman -Q mingw-w64-x86_64-libaacs
  pacman -Q mingw-w64-x86_64-libbdplus
  pacman -Q mingw-w64-x86_64-libdvdcss
} > "$stage/WINDOWS-NATIVE-PACKAGE-VERSIONS.txt"

echo "PARITY_MINGW_BIN=$(cygpath -w /mingw64/bin)" >> "$GITHUB_ENV"
echo "PARITY_OBJDUMP=$(cygpath -w /mingw64/bin/objdump.exe)" >> "$GITHUB_ENV"
echo 'PASS: libbluray 1.3.4; libaacs 0.11.1; libbdplus 0.2.0; libdvdcss 1.6.0'
echo 'No BDInfo binary is staged. Navigator compiled from unchanged muKsMaTT source.'
