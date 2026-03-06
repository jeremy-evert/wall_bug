import subprocess
from pathlib import Path
from datetime import datetime


def run(args):
    recordings_dir = Path("data/recordings")
    recordings_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = recordings_dir / f"note_{timestamp}.wav"

    print(f"Recording to {outfile}")
    print("Press Ctrl+C to stop recording")

    try:
        subprocess.run(
            [
                "arecord",
                "-f",
                "cd",
                "-t",
                "wav",
                str(outfile),
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\nRecording stopped.")

    print("Saved recording:", outfile)
