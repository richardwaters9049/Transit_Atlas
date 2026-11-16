#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/target/release/bundle/macos/Transit Atlas.app"
AUTOMATION="$ROOT/scripts/macos-study-ui-test.applescript"
CAMERA_AUTOMATION="$ROOT/scripts/macos-study-camera.swift"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This GUI test requires macOS." >&2
  exit 2
fi

if pgrep -x transit-atlas >/dev/null 2>&1; then
  echo "Close Transit Atlas before running this test. The harness launches a fresh app process." >&2
  exit 2
fi

if ! osascript -e 'tell application "System Events" to get UI elements enabled' >/dev/null 2>&1; then
  echo "macOS Accessibility permission is required for System Events UI scripting." >&2
  echo "Enable your terminal or automation host in System Settings > Privacy & Security > Accessibility." >&2
  exit 2
fi

cd "$ROOT/desktop"
bun run tauri build --bundles app --config '{"bundle":{"active":true}}'

if [[ ! -d "$APP" ]]; then
  echo "Tauri build completed without producing the expected app bundle: $APP" >&2
  exit 1
fi

TEST_DIR="$(mktemp -d /tmp/transit-atlas-study-ui.XXXXXX)"
STUDY="$TEST_DIR/K00115.03.atlas.json"
INVALID="$TEST_DIR/K00115.03.invalid.atlas.json"
CAMERA_BASELINE="$TEST_DIR/camera-baseline.png"
CAMERA_ROTATED="$TEST_DIR/camera-rotated.png"
CAMERA_RESTORED="$TEST_DIR/camera-restored.png"

APP_PID=""
cleanup() {
  osascript -e 'tell application "System Events" to tell process "transit-atlas" to quit' >/dev/null 2>&1 || true
  if [[ -n "$APP_PID" ]]; then
    for _ in {1..8}; do
      kill -0 "$APP_PID" >/dev/null 2>&1 || return 0
      sleep 0.25
    done
    kill "$APP_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

open -n "$APP"
for _ in {1..40}; do
  APP_PID="$(pgrep -n -x transit-atlas || true)"
  [[ -n "$APP_PID" ]] && break
  sleep 0.25
done
if [[ -z "$APP_PID" ]]; then
  echo "The Transit Atlas app process did not start." >&2
  exit 1
fi
osascript "$AUTOMATION" save "$STUDY" "$TEST_DIR"
swift "$CAMERA_AUTOMATION" capture "$CAMERA_BASELINE"
swift "$CAMERA_AUTOMATION" rotate "$CAMERA_ROTATED"
osascript "$AUTOMATION" restore "$STUDY"
swift "$CAMERA_AUTOMATION" capture "$CAMERA_RESTORED"
swift "$CAMERA_AUTOMATION" compare "$CAMERA_BASELINE" "$CAMERA_ROTATED" "$CAMERA_RESTORED"

python3 - "$STUDY" "$INVALID" <<'PY'
import copy
import json
import pathlib
import sys

study_path = pathlib.Path(sys.argv[1])
invalid_path = pathlib.Path(sys.argv[2])
document = json.loads(study_path.read_text())

assert document["schema"] == "transit-atlas.study"
assert document["version"] == 2
assert document["selection"]["candidate"] == "K00115.03"
assert document["selection"]["neighbour"] == "K02961.01"
assert len(document["provenance"]["light_curves"]) == 2

camera = document["selection"]["camera"]
assert camera is not None
assert len(camera["position"]) == 3
assert len(camera["target"]) == 3

tampered = copy.deepcopy(document)
tampered["provenance"]["light_curves"][0]["processing_fingerprint"] = "0" * 64
invalid_path.write_text(json.dumps(tampered, indent=2) + "\n")
print("PASS: saved schema, candidate/reference provenance and camera tuple validated.")
print(f"PASS: created tampered replay fixture at {invalid_path}")
PY

osascript "$AUTOMATION" failure "$INVALID"

echo "PASS: native macOS study save/open, camera restoration and fingerprint-failure UI checks completed."
echo "Test artefacts retained at: $TEST_DIR"
