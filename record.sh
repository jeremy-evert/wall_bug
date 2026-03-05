#!/usr/bin/env bash

OUTPUT=${1:-recording.wav}

echo "Recording audio..."
echo "Press CTRL+C to stop."

ffmpeg -f alsa -i default -ar 16000 -ac 1 "$OUTPUT"
