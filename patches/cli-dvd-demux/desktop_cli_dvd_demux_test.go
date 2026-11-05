//go:build linux || windows

package main

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestDVDCLIAdvancedSelectionHonorsTitleStreamsAndChapters(t *testing.T) {
	var p ffprobeResult
	if err := json.Unmarshal([]byte(`{"streams":[{"index":0,"codec_name":"mpeg2video","codec_type":"video"},{"index":1,"codec_name":"ac3","codec_type":"audio"},{"index":2,"codec_name":"dvd_subtitle","codec_type":"subtitle"}]}`), &p); err != nil {
		t.Fatal(err)
	}
	selected, err := selectCLIAdvancedDVDStreams("dvd.iso", 3, p, true, []int{2, 0}, true)
	if err != nil || len(selected) != 3 {
		t.Fatalf("selected=%+v err=%v", selected, err)
	}
	if selected[0].Track.Index != 0 || selected[1].Track.Index != 2 || selected[2].Track.Kind != "chapters" {
		t.Fatalf("wrong tracks/chapters: %+v", selected)
	}
	for _, row := range selected {
		if row.Path != "dvd.iso" || row.Track.DVDTitle != 3 || row.BluRay {
			t.Fatalf("wrong source/title: %+v", row)
		}
	}
	noChapters, err := selectCLIAdvancedDVDStreams("dvd.iso", 3, p, true, []int{1}, false)
	if err != nil || len(noChapters) != 1 || noChapters[0].Track.Kind != "audio" {
		t.Fatalf("audio-only selection: %+v %v", noChapters, err)
	}
	all, err := selectCLIAdvancedDVDStreams("dvd.iso", 3, p, false, nil, true)
	if err != nil || len(all) != 3 {
		t.Fatalf("all tracks without chapters: %+v %v", all, err)
	}
	for _, invalid := range [][]int{{99}, {0, 99}} {
		if _, err := selectCLIAdvancedDVDStreams("dvd.iso", 3, p, true, invalid, true); err == nil {
			t.Fatalf("accepted invalid index %v", invalid)
		}
	}
}

func TestDVDCLIExamplesUseTwoExistingDemuxPaths(t *testing.T) {
	examples := dvdCLIExamples()
	if len(examples) != 2 || !strings.Contains(examples[0], "muksmatt-cli demux ") ||
		!strings.Contains(examples[1], "muksmatt-cli advanced demux ") {
		t.Fatalf("missing DVD demux presets: %v", examples)
	}
	for _, example := range examples {
		parsed, err := splitCLICommand(example)
		if err != nil || len(parsed) < 5 || strings.Contains(example, ".mkv") {
			t.Fatalf("invalid direct DVD demux example %q: %v", example, err)
		}
	}
}

// Optional integration test: source must be an authored, unencrypted DVD.
// Both GUI demux functions are invoked through their exact shared code paths.
func TestDVDCLIBothModesAuthoredFixture(t *testing.T) {
	source := os.Getenv("MATTRIP_TEST_DEMUX_DVD")
	if source == "" {
		t.Skip("set MATTRIP_TEST_DEMUX_DVD to an authored DVD directory")
	}
	for _, tc := range []struct {
		name string
		advanced bool
	}{{"remux-demux", false}, {"advanced", true}} {
		t.Run(tc.name, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
			defer cancel()
			tools, err := desktopCLITools(ctx, false)
			if err != nil { t.Fatal(err) }
			out := t.TempDir()
			var final string
			if tc.advanced {
				selected, err := cliAdvancedDVDSelection(ctx, tools.ffprobe, source, 1, nil, true)
				if err != nil { t.Fatal(err) }
				final, err = demuxMerger(ctx, tools, selected, out, "mpeg2")
			} else {
				final, err = demuxTab(ctx, tools, source, 1, out, nil, true, "mpeg2")
			}
			if err != nil { t.Fatal(err) }
			var video, audio bool
			err = filepath.WalkDir(final, func(path string, entry os.DirEntry, err error) error {
				if err != nil { return err }
				if strings.HasSuffix(strings.ToLower(path), ".mkv") { t.Errorf("unexpected MKV: %s", path) }
				if !entry.IsDir() {
					st, err := entry.Info(); if err != nil { return err }
					if st.Size() == 0 { t.Errorf("empty output: %s", path) }
					if strings.HasSuffix(path, ".mpeg2") { video = true }
					if strings.HasSuffix(path, ".ac3") { audio = true }
				}
				return nil
			})
			if err != nil { t.Fatal(err) }
			if !video || !audio { t.Fatalf("missing streams: video=%v audio=%v in %s", video,audio,final) }
		})
	}
}
