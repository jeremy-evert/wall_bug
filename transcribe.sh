#!/usr/bin/env bash

FILE=$1

if [ -z "$FILE" ]; then
    echo "Usage: ./transcribe.sh audiofile"
    exit 1
fi

echo "Preparing audio..."

ffmpeg -i "$FILE" -ar 16000 -ac 1 temp.wav -y >/dev/null 2>&1

echo "Running transcription..."

./whisper.cpp/main \
  -m whisper.cpp/models/ggml-base.en.bin \
  -f temp.wav \
  -otxt

echo
echo "Transcript saved as temp.wav.txt"
