#!/usr/bin/env bash

set -e

echo "================================="
echo "wall_bug setup starting"
echo "================================="

# install dependencies
if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y git gcc-c++ make cmake ffmpeg
elif command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y git build-essential cmake ffmpeg
else
    echo "Unsupported package manager"
    exit 1
fi

echo
echo "Cloning whisper.cpp..."

if [ ! -d whisper.cpp ]; then
    git clone https://github.com/ggerganov/whisper.cpp
fi

cd whisper.cpp

echo
echo "Building whisper.cpp..."

make

echo
echo "Downloading model..."

./models/download-ggml-model.sh base.en

cd ..

mkdir -p models

echo
echo "Setup complete."
echo "Use:"
echo "./record_and_transcribe.sh"
