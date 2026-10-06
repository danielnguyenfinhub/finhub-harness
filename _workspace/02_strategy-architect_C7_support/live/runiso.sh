#!/usr/bin/env bash
# runiso.sh <fxdir> <tag> : run.sh inside a private mount namespace: / read-only; only the fixture, ~/.claude, ~/.claude.json and the session dir are writable (the judge round 2 approach)
FX=$(cd "$1" && pwd); TAG=$2
TD=/tmp/claude-0/$(echo "$FX" | tr / -); mkdir -p "$TD"
unshare -m bash -c '
mount --make-rprivate /
mount --bind "$1" "$1"
mount --bind "$3" "$3"
mount --bind /root/.claude /root/.claude
mount --bind /root/.claude.json /root/.claude.json
mount -o remount,ro,bind /
cd "$1" && ./run.sh "$2"
' _ "$FX" "$TAG" "$TD"
