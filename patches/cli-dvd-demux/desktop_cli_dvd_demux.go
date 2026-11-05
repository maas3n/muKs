//go:build linux || windows

package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// DVD DEMUX CLI delegates extraction to the same two functions used by the
// desktop GUI. This file only parses user options and builds ADVANCED selections;
// it never remuxes a DVD or changes the FFmpeg processing engine.
func cliDVDDemux(ctx context.Context, args []string, advanced bool) {
	command := "demux"
	if advanced {
		command = "advanced demux"
	}
	fs := flag.NewFlagSet(command, flag.ExitOnError)
	titleN := fs.Int("title", 0, "DVD title number (0 = longest)")
	output := fs.String("output", "", "existing output directory (default: beside ISO/VIDEO_TS)")
	streams := fs.String("streams", "", "comma-separated absolute stream indexes (default: all media)")
	video := fs.String("video", "mpeg2", "MPEG-2 video output: mpeg2 or vob")
	noChapters := fs.Bool("no-chapters", false, "do not export Chapters.txt")
	fs.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: muksmatt-cli %s [--title N] [--output DIR] [--streams 0,1,2] [--video mpeg2|vob] [--no-chapters] SOURCE\n", command)
	}
	_ = fs.Parse(cliFlagsFirst(args))
	if fs.NArg() != 1 {
		fs.Usage()
		os.Exit(2)
	}
	fs.Visit(func(f *flag.Flag) {
		if f.Name == "streams" && *streams == "" {
			fatalIf(errors.New("--streams must not be empty"))
		}
	})
	if *video != "mpeg2" && *video != "vob" {
		fatalIf(fmt.Errorf("--video must be mpeg2 or vob (got %q)", *video))
	}
	indexes, err := parseCLIStreams(*streams)
	fatalIf(err)
	source, err := resolveDVDSource(fs.Arg(0))
	fatalIf(err)
	outDir := strings.TrimSpace(*output)
	if outDir == "" {
		outDir, err = defaultDVDOutputDir(source.Input)
		fatalIf(err)
	}
	outDir, err = filepath.Abs(outDir)
	fatalIf(err)
	fatalIf(validateOutputDir(outDir))
	tools := mustTools(ctx, false)
	title := mustResolveTitle(ctx, source.Input, *titleN, tools)
	fmt.Fprintf(os.Stderr, "Demuxing DVD title %d directly (no intermediate MKV).\n", title.Number)
	var final string
	if advanced {
		selected, selectErr := cliAdvancedDVDSelection(ctx, tools.ffprobe, source.Input, title.Number, indexes, !*noChapters)
		fatalIf(selectErr)
		final, err = demuxMerger(ctx, tools, selected, outDir, *video)
	} else {
		final, err = demuxTab(ctx, tools, source.Input, title.Number, outDir, indexes, !*noChapters, *video)
	}
	fatalIf(err)
	fmt.Println(final)
}

// Build ADVANCED GUI-compatible stream rows for the requested title. The GUI's
// probeMergerFile() always chooses the longest title; explicit CLI --title must
// probe that specific title instead, so stream indexes cannot silently diverge.
func cliAdvancedDVDSelection(ctx context.Context, ffprobe, source string, title int, indexes []int, chapters bool) ([]mergerStream, error) {
	args := appendDesktopDVDInput([]string{"-v", "error", "-show_streams", "-show_chapters", "-of", "json"}, title, source)
	data, err := runMergerCommand(ctx, ffprobe, args...)
	if err != nil {
		return nil, err
	}
	var tracks ffprobeResult
	if err = json.Unmarshal(data, &tracks); err != nil {
		return nil, err
	}
	var chapterRows ffprobeChapterResult
	if err = json.Unmarshal(data, &chapterRows); err != nil {
		return nil, err
	}
	return selectCLIAdvancedDVDStreams(source, title, tracks, len(chapterRows.Chapters) > 0, indexes, chapters)
}

// Only track selection and row formatting live here; all extraction, output
// naming and cleanup remain in the unmodified demuxMerger() implementation.
func selectCLIAdvancedDVDStreams(source string, title int, probe ffprobeResult, hasChapters bool, indexes []int, chapters bool) ([]mergerStream, error) {
	wanted := make(map[int]bool, len(indexes))
	for _, index := range indexes {
		wanted[index] = true
	}
	var selected []mergerStream
	for _, raw := range probe.Streams {
		if raw.CodecType != "video" && raw.CodecType != "audio" && raw.CodecType != "subtitle" {
			continue
		}
		if indexes != nil && !wanted[raw.Index] {
			continue
		}
		selected = append(selected, mergerStream{Path: source, Track: trackOption{
			DVDTitle: title, Index: raw.Index, Kind: raw.CodecType, Codec: raw.CodecName,
			Language: raw.Tags["language"], Title: raw.Tags["title"],
			Width: raw.Width, Height: raw.Height, Channels: raw.Channels, ChannelLayout: raw.ChannelLayout,
		}})
		delete(wanted, raw.Index)
	}
	if len(wanted) > 0 {
		return nil, errors.New("selected stream is no longer available; scan again")
	}
	if len(selected) == 0 {
		return nil, errors.New("select at least one video, audio, or subtitle stream")
	}
	if chapters && hasChapters {
		selected = append(selected, mergerStream{Path: source, Track: trackOption{DVDTitle: title, Index: -1, Kind: "chapters"}})
	}
	return selected, nil
}

// The CLI-tab buttons populate valid examples; actual extraction is always
// performed by the normal embedded muksmatt-cli command runner.
func dvdCLIExamples() []string {
	return []string{
		`muksmatt-cli demux --title 1 --output "OUTPUT_DIR" --video mpeg2 "SOURCE"`,
		`muksmatt-cli advanced demux --title 1 --output "OUTPUT_DIR" --video mpeg2 "SOURCE"`,
	}
}
