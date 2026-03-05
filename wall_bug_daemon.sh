#!/usr/bin/env bash

REPO=~/Nora/git/wall_bug
BIN=$REPO/whisper.cpp/build/bin/whisper-cli
MODEL=$REPO/whisper.cpp/models/ggml-base.en.bin
NOTES=~/voice_notes
mkdir -p "$NOTES"

STATE="idle"
FILE=""

echo "WallBug voice daemon started"

xinput test-xi2 --root | while read line; do

if [[ "$line" == *"RawKeyPress"* ]]; then
    read next
    KEY=$(echo $next | awk '{print $2}')

    # keycode 49 is usually the ` key
    if [[ "$KEY" == "49" ]]; then

        if [[ "$STATE" == "idle" ]]; then
            FILE=$(date +%F_%H-%M-%S).wav
            echo "Recording..."
            ffmpeg -loglevel quiet -f alsa -i default -ar 16000 -ac 1 "$FILE" &
            PID=$!
            STATE="recording"

        else
            echo "Stopping..."
            kill $PID
            ffmpeg -loglevel quiet -i "$FILE" -ar 16000 -ac 1 temp.wav -y
            $BIN -m $MODEL -f temp.wav -otxt >/dev/null

            NOTE="$NOTES/$(date +%F).md"
            echo "### $(date +%H:%M:%S)" >> "$NOTE"
            cat temp.wav.txt >> "$NOTE"
            echo "" >> "$NOTE"

            STATE="idle"
            echo "Saved to $NOTE"
        fi
    fi
fi

done
