#!/usr/bin/env bash
# Download static ffmpeg + ffprobe for Apple Silicon into the given folder and check them.
# Used by the GitHub Actions macOS build. Tries a few well-known static build hosts.
set -euo pipefail
dest="${1:?usage: fetch_ffmpeg.sh DEST_DIR}"
mkdir -p "$dest"
tmp="$(mktemp -d)"

fetch_zip() { # url name
  local url="$1" name="$2"
  rm -rf "$tmp/$name" "$tmp/$name.zip"
  curl -fsSL --retry 3 -o "$tmp/$name.zip" "$url" || return 1
  mkdir -p "$tmp/$name"
  unzip -o -q "$tmp/$name.zip" -d "$tmp/$name" || return 1
  local found
  found="$(find "$tmp/$name" -type f -name "$name" | head -1)"
  [ -n "$found" ] || return 1
  cp "$found" "$dest/$name"
}

riedl() {
  echo "trying ffmpeg.martin-riedl.de"
  fetch_zip "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip" ffmpeg &&
    fetch_zip "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffprobe.zip" ffprobe
}

osxexperts() {
  echo "trying osxexperts.net"
  for v in 80 71 70; do
    if fetch_zip "https://www.osxexperts.net/ffmpeg${v}arm.zip" ffmpeg && fetch_zip "https://www.osxexperts.net/ffprobe${v}arm.zip" ffprobe; then
      return 0
    fi
  done
  return 1
}

riedl || osxexperts || { echo "::error::could not download a static ffmpeg for macOS arm64"; exit 1; }
chmod +x "$dest/ffmpeg" "$dest/ffprobe"
xattr -c "$dest/ffmpeg" "$dest/ffprobe" 2>/dev/null || true
file "$dest/ffmpeg"
"$dest/ffmpeg" -hide_banner -version | head -1
"$dest/ffprobe" -hide_banner -version | head -1
"$dest/ffmpeg" -hide_banner -encoders 2>/dev/null | grep -q libx264 || { echo "::error::this ffmpeg has no libx264"; exit 1; }
if "$dest/ffmpeg" -hide_banner -filters 2>/dev/null | grep -q " zscale "; then
  echo "zscale: yes (HDR is tone-mapped properly)"
else
  echo "::warning::this ffmpeg has no zscale filter, HDR clips will use the rough fallback"
fi
# make sure linked libraries are all system ones (a truly static build)
otool -L "$dest/ffmpeg" | tail -n +2 | grep -v -E "/usr/lib/|/System/" && { echo "::error::ffmpeg links to non-system libraries"; exit 1; } || true
