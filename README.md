# wall_bug

Simple Linux audio transcription tool.

Record from microphone and transcribe locally using Whisper.

No cloud services required at runtime.

## Dependencies

Wall_Bug depends on these system tools/services:

- `ffmpeg` on `PATH` (recording + audio conversion)
- `whisper-cli` on `PATH` (local transcription engine)
- PulseAudio or PipeWire (for default microphone input: `-f pulse -i default`)

Example install on Debian/Ubuntu:

- `sudo apt-get install -y ffmpeg`
- Install `whisper.cpp` and make sure `whisper-cli` is on `PATH`: https://github.com/ggml-org/whisper.cpp

## Setup

git clone git@github.com:jeremy-evert/wall_bug.git
cd wall_bug
chmod +x *.sh
./setup.sh
