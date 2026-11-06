#!/usr/bin/env python3
"""Read-only provenance hunt for ORIGINAL BtbN Windows FFmpeg 2026-09-08 ZIP.

Never substitute versions, never download arbitrary mirrored executables,
never modify muKsMaTT source or release. Results are metadata only.
"""
import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TAG = "autobuild-2026-09-08-23-15"
REV = "N-126479-g08cd8df29d"
ASSET = f"ffmpeg-{REV}-win64-gpl-shared.zip"
OWNER = "BtbN/FFmpeg-Builds"
ORIGIN = f"https://github.com/{OWNER}/releases/download/{TAG}/{ASSET}"
OUT = Path("ffmpeg-provenance")
OUT.mkdir(exist_ok=True)
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"User-Agent": "muKsMaTT-Windows-FFmpeg-Provenance-Audit",
           "Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = "Bearer " + TOKEN

def fetch(url, maxbytes=3000000, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(maxbytes + 1)
            return {"status": response.status, "url": response.url,
                    "content_type": response.headers.get("Content-Type"),
                    "truncated": len(raw) > maxbytes,
                    "body": raw[:maxbytes].decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "url": url,
                "message": e.read(1000).decode("utf-8", "replace")}
    except Exception as e:
        return {"status": "network error", "url": url,
                "message": type(e).__name__ + ": " + str(e)[:240]}

def github_api(endpoint):
    res = fetch("https://api.github.com/" + endpoint)
    try:
        return res, json.loads(res.get("body", "{}"))
    except ValueError:
        return res, {}

def summarize_api():
    origin, data = github_api(f"repos/{OWNER}/releases/tags/{TAG}")
    print("ORIGINAL RELEASE status:", origin["status"])
    report = {"origin": {"tag": TAG, "asset": ASSET, "url": ORIGIN,
                         "release_api_http_status": origin["status"]}}
    if isinstance(data, dict) and data.get("assets"):
        entries = [a for a in data["assets"] if a.get("name") == ASSET]
        report["origin"]["matching_assets"] = [
            {"id": a.get("id"), "name": a.get("name"), "size": a.get("size"),
             "digest": a.get("digest"), "browser_download_url": a.get("browser_download_url")}
            for a in entries]
        print("ORIGINAL release matching assets:", report["origin"]["matching_assets"])
    else:
        report["origin"]["api_result"] = str(data.get("message", ""))[:200]
    return report

def check_wayback(report):
    targets = [
        ORIGIN,
        f"https://github.com/{OWNER}/releases/download/{TAG}/checksums.sha256"
    ]
    report["wayback"] = []
    for target in targets:
        params = urllib.parse.urlencode({"url": target, "timestamp": "20260920"})
        url = "https://archive.org/wayback/available?" + params
        response = fetch(url, maxbytes=100000)
        entry = {"target": target, "http_status": response["status"]}
        if response["status"] == 200:
            try:
                data = json.loads(response.get("body", "{}"))
                entry["snapshots"] = data.get("archived_snapshots", {})
            except ValueError:
                entry["response"] = response.get("body", "")[:500]
        else:
            entry["error"] = response.get("message", "")[:200]
        report["wayback"].append(entry)
        print("WAYBACK:", target.split("/")[-1], json.dumps(entry)[:700])
    # Query CDX for the ORIGINAL asset URL; a 200 ZIP snapshot would be
    # relevant, but HTML error snapshots are NOT a binary archive.
    cdx = "https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(
        {"url": ORIGIN, "output": "json", "filter": "statuscode:200",
         "collapse": "digest", "fl": "timestamp,original,statuscode,mimetype,digest,length"})
    result = fetch(cdx, maxbytes=50000)
    report["wayback_cdx"] = {"http_status": result["status"],
                            "body": result.get("body", "")[:12000],
                            "error": result.get("message", "")[:200]}
    print("CDX status:", result["status"], "result:", result.get("body", "")[:300])

def scan_action_artifacts(report):
    # Original build was 2026-09-08 at 23:15 UTC; query all jobs on that day.
    created = urllib.parse.quote("2026-09-08T00:00:00Z..2026-09-09T23:59:59Z", safe="")
    r, data = github_api(f"repos/{OWNER}/actions/runs?created={created}&per_page=100")
    report["github_actions"] = {"runs_http_status": r["status"], "matches": []}
    if not isinstance(data, dict):
        return
    runs = data.get("workflow_runs", [])
    print("GITHUB ACTIONS historical runs:", len(runs), "total_count", data.get("total_count"))
    print("MATCHING original commit/release runs:")
    for run in runs:
        created = run.get("created_at", "")
        name = run.get("name", "")
        job = {"id": run.get("id"), "name": name, "created_at": created,
               "head_sha": run.get("head_sha"), "run_number": run.get("run_number"),
               "event": run.get("event"), "conclusion": run.get("conclusion"),
               "html_url": run.get("html_url"), "artifacts": []}
        if "2026-09-08" not in created and "2026-09-09" not in created:
            continue
        if len(report["github_actions"]["matches"]) >= 30:
            break
        art_status, art = github_api(
            f"repos/{OWNER}/actions/runs/{run.get('id')}/artifacts?per_page=100")
        if isinstance(art, dict):
            job["artifact_query_status"] = art_status["status"]
            job["artifacts"] = [
                {"id": x.get("id"), "name": x.get("name"), "size_in_bytes": x.get("size_in_bytes"),
                 "expired": x.get("expired"), "expires_at": x.get("expires_at")}
                for x in art.get("artifacts", []) if x.get("id")]
        report["github_actions"]["matches"].append(job)
        print(json.dumps(job)[:2000])
    if data.get("total_count", 0) > 100:
        report["github_actions"]["truncated"] = True

def main():
    report = summarize_api()
    check_wayback(report)
    scan_action_artifacts(report)
    (OUT / "original-ffmpeg-archival-search.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("STATUS: Metadata search completed. No unverified binaries staged.")
    print("EVIDENCE: An authentic archive requires real ZIP bytes plus verifiable SHA256 and build flags.")

if __name__ == "__main__":
    main()
