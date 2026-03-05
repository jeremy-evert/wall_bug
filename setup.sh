#!/usr/bin/env bash

set -e

echo
echo "================================="
echo "wall_bug setup starting"
echo "================================="
echo

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

############################
# install dependencies
############################

echo "Installing dependencies..."

if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y git gcc-c++ make cmake ffmpeg
elif command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y git build-essential cmake ffmpeg
else
    echo "Unsupported package manager"
    exit 1
fi

############################
# clone whisper.cpp
############################

cd "$REPO_DIR"

if [ ! -d whisper.cpp ]; then
    echo
    echo "Cloning whisper.cpp..."
    git clone https://github.com/ggerganov/whisper.cpp
fi

############################
# build whisper.cpp
############################

echo
echo "Building whisper.cpp..."

cd whisper.cpp

cmake -B build
cmake --build build --config Release

############################
# download model
############################

echo
echo "Downloading model..."

./models/download-ggml-model.sh base.en

cd "$REPO_DIR"

############################
# ensure scripts executable
############################

echo
echo "Fixing script permissions..."

chmod +x *.sh

############################
# create directories
############################

mkdir -p recordings
mkdir -p transcripts
mkdir -p notes

############################
# verify build
############################

BIN="$REPO_DIR/whisper.cpp/build/bin/whisper-cli"

if [ ! -f "$BIN" ]; then
    echo
    echo "ERROR: whisper binary not found"
    exit 1
fi

echo
echo "whisper.cpp installed successfully"

############################
# install daemon service
############################

echo
echo "Installing systemd user service..."

mkdir -p ~/.config/systemd/user

SERVICE=~/.config/systemd/user/wallbug.service

cat <<EOF > $SERVICE
[Unit]
Description=Wall Bug Audio Transcription Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/wall_bug_daemon.sh
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload

echo
echo "Service installed."

############################
# instructions
############################

echo
echo "================================="
echo "Setup complete"
echo "================================="
echo
echo "To start the daemon:"
echo
echo "  systemctl --user start wallbug"
echo
echo "To enable at login:"
echo
echo "  systemctl --user enable wallbug"
echo
echo "To view logs:"
echo
echo "  journalctl --user -u wallbug -f"
echo
