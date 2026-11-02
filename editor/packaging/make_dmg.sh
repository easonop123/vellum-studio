#!/usr/bin/env bash
# Wrap dist/Vellum Editor.app into a drag-to-Applications .dmg.
set -euo pipefail
app="${1:?usage: make_dmg.sh 'path/to/Vellum Editor.app' out.dmg}"
out="${2:?usage: make_dmg.sh app out.dmg}"
stage="$(mktemp -d)/Vellum Editor"
mkdir -p "$stage"
cp -R "$app" "$stage/"
ln -s /Applications "$stage/Applications"
cat > "$stage/READ ME FIRST.txt" <<'EOF'
1. Drag "Vellum Editor" onto the Applications folder.
2. The first time: open Applications, right-click Vellum Editor and choose Open.
   If macOS still says it can't be opened, go to System Settings > Privacy & Security,
   scroll down and click "Open Anyway" next to Vellum Editor.
3. After that it opens normally with a double-click.
EOF
rm -f "$out"
hdiutil create -volname "Vellum Editor" -srcfolder "$stage" -ov -format UDZO -fs HFS+ "$out"
ls -lh "$out"
