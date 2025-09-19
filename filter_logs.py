import argparse
import os
import sys
import tempfile
from pathlib import Path

def main():
    """
    Reads logs from the named pipes and prints them to the console.
    """
    parser = argparse.ArgumentParser(description="Filter and display logs from browser-use.")
    parser.add_argument("--session-id", required=True, help="The session ID of the agent.")
    args = parser.parse_args()

    base_dir = tempfile.gettempdir()
    suffix = args.session_id[-4:]
    pipe_dir = Path(base_dir) / f"buagent.{suffix}"

    pipes = {
        "agent": pipe_dir / "agent.pipe",
        "cdp": pipe_dir / "cdp.pipe",
        "events": pipe_dir / "events.pipe",
    }

    print(f"Tailing logs from {pipe_dir}...")

    try:
        for name, path in pipes.items():
            if not os.path.exists(path):
                print(f"Pipe not found: {path}", file=sys.stderr)
                continue

            print(f"--- {name} ---")
            with open(path) as f:
                while True:
                    line = f.readline()
                    if not line:
                        break
                    print(line, end="")
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()