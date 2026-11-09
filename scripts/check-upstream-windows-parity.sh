#!/usr/bin/env bash
set -euo pipefail
tag='autobuild-2026-09-08-23-15'
asset='ffmpeg-N-126479-g08cd8df29d-win64-gpl-shared.zip'
echo '=== Upstream release availability: exact Linux-matched 2026-09-08 FFmpeg ==='
python3 - <<'PY'
import json,urllib.request,urllib.error
tag='autobuild-2026-09-08-23-15'
u=f'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/{tag}'
req=urllib.request.Request(u, headers={'User-Agent':'muksmatt-verify','Accept':'application/vnd.github+json'})
try:
 with urllib.request.urlopen(req,timeout=30) as r: obj=json.load(r)
 print('API_RELEASE_TAG',obj.get('tag_name'))
 print('API_ASSETS_COUNT',len(obj.get('assets',[])))
 for a in obj.get('assets',[]):
  if 'checksum' in a['name'].lower() or 'N-126479-g08cd8df29d-win64-gpl-shared' in a['name']:
   print('API_MATCH',a['name'],a.get('id'),a.get('digest'),a.get('size'))
except Exception as e: print('API_RELEASE_ERROR',type(e).__name__,str(e))
PY
for url in \
  "https://github.com/BtbN/FFmpeg-Builds/releases/download/$tag/checksums.sha256" \
  "https://github.com/BtbN/FFmpeg-Builds/releases/download/$tag/$asset" \
  "https://repo.msys2.org/mingw/mingw64/mingw-w64-x86_64-libbluray-1.3.4-1-any.pkg.tar.zst" \
  "https://repo.msys2.org/mingw/mingw64/mingw-w64-x86_64-libbluray-1.3.4-1-any.pkg.tar.zst.sig" \
  'https://mediaarea.net/download/binary/mediainfo/26.05/MediaInfo_CLI_26.05_Windows_x64.zip'; do
  echo "CHECK $url"
  curl -sSL --retry 1 --max-time 15 -o /dev/null -w 'HTTP %{http_code} bytes %{size_download} redirect %{url_effective}\n' -r '0-0' "$url" || echo 'HTTP request error'
done
