#!/usr/bin/env python3
"""Apply only the reviewed DVD DEMUX CLI and CLI-tab feature to v.0.0.2 source.

The original source lives in a GitHub release asset, not in this repo's main
Git tree. All substitutions are exact and fail closed if the source changes.
No media engine source file is modified.
"""
import shutil
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply-dvd-demux-cli.py EXTRACTED_SOURCE_ROOT")
root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[1]

def replace(rel, old, new):
    path = root / rel
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match in {rel}: found {count}")
    path.write_text(text.replace(old, new, 1))
    print("Patched CLI/UI:", rel)

replace("src/desktop_cli.go",
    '\tcase "remux":\n\t\tcliRemux(ctx, os.Args[2:])\n\tcase "bluray":',
    '\tcase "remux":\n\t\tcliRemux(ctx, os.Args[2:])\n'
    '\tcase "demux":\n\t\tcliDVDDemux(ctx, os.Args[2:], false)\n'
    '\tcase "advanced":\n'
    '\t\tif len(os.Args) < 3 || os.Args[2] != "demux" {\n'
    '\t\t\tfmt.Fprintln(os.Stderr, "Usage: muksmatt-cli advanced demux [--title N] [--output DIR] [--streams 0,1,2] [--video mpeg2|vob] [--no-chapters] SOURCE")\n'
    '\t\t\tos.Exit(2)\n\t\t}\n'
    '\t\tcliDVDDemux(ctx, os.Args[3:], true)\n'
    '\tcase "bluray":')
replace("src/desktop_cli.go",
    '  muksmatt-cli remux [--title N] [--output DIR] [--no-chapters] [--streams 0,1,2] SOURCE\n',
    '  muksmatt-cli remux [--title N] [--output DIR] [--no-chapters] [--streams 0,1,2] SOURCE\n'
    '  muksmatt-cli demux [--title N] [--output DIR] [--streams 0,1,2] [--video mpeg2|vob] [--no-chapters] SOURCE\n'
    '  muksmatt-cli advanced demux [--title N] [--output DIR] [--streams 0,1,2] [--video mpeg2|vob] [--no-chapters] SOURCE\n')
replace("src/desktop_cli.go",
    'If --title is omitted, muKsMaTT scans the disc and selects the longest title.\n',
    'If --title is omitted, muKsMaTT scans the disc and selects the longest title.\n'
    'Both DVD DEMUX commands export directly from the DVD without creating an MKV.\n'
    '"demux" uses REMUX/DEMUX tab output; "advanced demux" uses ADVANCED tab output.\n'
    '--video mpeg2 exports elementary MPEG-2; --video vob writes video in .VOB.\n'
    '--streams uses absolute stream indexes from metadata; --no-chapters skips chapter files.\n')

replace("src/cli_ui_linux.go",
    '\texamples := blurayCLIExamples()\n\tpresets := container.NewHBox(',
    '\texamples := blurayCLIExamples()\n\tdvdExamples := dvdCLIExamples()\n'
    '\tblurayPresets := container.NewHBox(')
replace("src/cli_ui_linux.go",
    '\t)\n\thelp := widget.NewLabel("DVD and Blu-ray CLI — choose an example, replace SOURCE/OUTPUT_DIR, then Run. Scan first; explicitly select the correct Blu-ray playlist (e.g. 00800). Use --help for all options.")',
    '\t)\n\tdvdPresets := container.NewHBox(\n'
    '\t\twidget.NewButton("DVD DEMUX (REMUX/DEMUX)", func() { command.SetText(dvdExamples[0]) }),\n'
    '\t\twidget.NewButton("DVD DEMUX (ADVANCED)", func() { command.SetText(dvdExamples[1]) }),\n'
    '\t)\n'
    '\thelp := widget.NewLabel("DVD and Blu-ray CLI — choose an example, replace SOURCE/OUTPUT_DIR, then Run. For DVD, use scan/metadata to select a title or streams; for Blu-ray, select the correct playlist (e.g. 00800). Use --help for all options.")')
replace("src/cli_ui_linux.go",
    'container.NewVBox(help, presets, command, container.NewHBox(run, stop))',
    'container.NewVBox(help, dvdPresets, blurayPresets, command, container.NewHBox(run, stop))')

replace("src/cli_ui_windows.go",
    '\tadd("BUTTON", "Blu-ray Scan", BS_PUSHBUTTON, 28, 204, 140, 30, cliFirstID+2)',
    '\tadd("BUTTON", "DVD DEMUX (Main)", BS_PUSHBUTTON, 28, 204, 180, 30, cliFirstID+6)\n'
    '\tadd("BUTTON", "DVD DEMUX (Advanced)", BS_PUSHBUTTON, 214, 204, 190, 30, cliFirstID+7)\n'
    '\tadd("BUTTON", "Blu-ray Scan", BS_PUSHBUTTON, 28, 240, 140, 30, cliFirstID+2)')
for old, new in [
    ('174, 204, 140, 30', '174, 240, 140, 30'),
    ('320, 204, 140, 30', '320, 240, 140, 30'),
    ('466, 204, 140, 30', '466, 240, 140, 30'),
    ('28, 250, 750, 314', '28, 286, 750, 278'),
]:
    replace("src/cli_ui_windows.go", old, new)
replace("src/cli_ui_windows.go",
    'if id >= cliFirstID+2 && id <= cliFirstID+5 {',
    'if (id >= cliFirstID+2 && id <= cliFirstID+5) || id == cliFirstID+6 || id == cliFirstID+7 {')
replace("src/cli_ui_windows.go",
    '\t\t\texamples := blurayCLIExamples()\n\t\t\tsetText(cliWindow.command, examples[id-cliFirstID-2])',
    '\t\t\tif id == cliFirstID+6 || id == cliFirstID+7 {\n'
    '\t\t\t\tsetText(cliWindow.command, dvdCLIExamples()[id-cliFirstID-6])\n'
    '\t\t\t} else {\n'
    '\t\t\t\tsetText(cliWindow.command, blurayCLIExamples()[id-cliFirstID-2])\n'
    '\t\t\t}')
replace("packaging/linux/standalone/main.go",
    'case "scan", "metadata", "remux", "bluray", "--batch", "--version", "--help", "tools", "doctor":',
    'case "scan", "metadata", "remux", "demux", "advanced", "bluray", "--batch", "--version", "--help", "tools", "doctor":')

for filename in ["desktop_cli_dvd_demux.go", "desktop_cli_dvd_demux_test.go"]:
    destination = root / "src" / filename
    if destination.exists():
        raise RuntimeError(f"Already exists: {destination}")
    shutil.copyfile(repo / "patches" / "cli-dvd-demux" / filename, destination)
    print("Added CLI/UI:", destination.relative_to(root))
print("Applied DVD DEMUX CLI feature; original media engine source unchanged")
