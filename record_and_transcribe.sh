#!/usr/bin/env bash

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILE="recording_$TIMESTAMP.wav"

echo
echo "================================="
echo "Recording..."
echo "Press CTRL+C when finished"
echo "================================="
echo

ffmpeg -f alsa -i default -ar 16000 -ac 1 "$FILE"

echo
echo "================================="
echo "Transcribing..."
echo "================================="
echo

ffmpeg -i "$FILE" -ar 16000 -ac 1 temp.wav -y >/dev/null 2>&1

./whisper.cpp/main \
  -m whisper.cpp/models/ggml-base.en.bin \
  -f temp.wav \
  -otxt

mv temp.wav.txt "$FILE.txt"

echo
echo "Transcript:"
echo "---------------------------------"
cat "$FILE.txt"
echo "---------------------------------"
echo
echo "Saved to: $FILE.txt"
