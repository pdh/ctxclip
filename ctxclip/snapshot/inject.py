"""snapshot debugger"""

import inspect
import os
import argparse
import sys
import tempfile
import subprocess
import re
from ctxclip.snapshot import debugger


def arg_parser(parser=None):
    """argument parsing"""
    if not parser:
        parser = argparse.ArgumentParser(
            description="Capture a debug snapshot at a specific line in a Python file"
        )
    parser.add_argument(
        "--file", required=True, help="Path to the Python file to analyze"
    )
    parser.add_argument(
        "--line-num",
        required=True,
        type=int,
        help="Line number where to capture the snapshot",
    )
    parser.add_argument("--label", default=None, help="Optional label for the snapshot")
    parser.add_argument(
        "--output-dir", default="debug_snapshots", help="Directory to store snapshots"
    )
    parser.add_argument(
        "--args", nargs="*", default=[], help="Arguments to pass to the target script"
    )
    return parser


def inject_snapshot_code(file_path, line_num, label=None, output_dir="debug_snapshots"):
    """injects the snapshot code to file_path:line_num"""
    source = inspect.getsource(debugger)
    # Read the original file
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    label_str = f'"{label}"' if label else "None"
    snapshot_line = (
        f"_snapshot_debugger.capture({label_str})  # Injected snapshot call\n"
    )
    # Determine indentation of the target line
    if line_num <= len(lines) and line_num > 0:
        # Get the indentation of the target line
        target_line = lines[line_num - 1] if line_num <= len(lines) else ""
        indentation = ""
        for char in target_line:
            if char in (" ", "\t"):
                indentation += char
            else:
                break
        # Check if the line ends with a colon (indicating a new block)
        if target_line.rstrip().endswith(":"):
            # If it's a new block, we need to add more indentation
            indentation += "    "  # Add 4 spaces for a new indentation level

        # Insert the snapshot call with proper indentation
        snapshot_line = f"{indentation}{snapshot_line}"
        if line_num <= len(lines):
            lines.insert(line_num, snapshot_line)
        else:
            lines.append(snapshot_line)
    else:
        # Handle invalid line numbers
        print(
            f"Warning: Line number {line_num} is out of range. Adding snapshot at the end."
        )
        lines.append(snapshot_line)

    # Create a temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".py", prefix="_snapshot_")
    os.close(temp_fd)

    # Combine the debugger code with the modified content
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(source + "\n" + "".join(lines))

    return temp_path


def extract_snapshot_path(output):
    """Extract the snapshot file path from the output"""
    match = re.search(r"DEBUG_SNAPSHOT_PATH: (.+)$", output, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def main(args: argparse.Namespace | None = None) -> None:
    """create snapshot cli"""
    if not args:
        parser = arg_parser()
        args = parser.parse_args()

    # Validate file exists
    if not os.path.isfile(args.file):
        print(f"Error: File {args.file} does not exist", file=sys.stderr)
        sys.exit(1)

    # Create a temporary modified file with the snapshot code injected
    temp_file = inject_snapshot_code(
        args.file, args.line_num, args.label, args.output_dir
    )

    try:
        # Run the modified file
        cmd = [sys.executable, temp_file] + args.args
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        # Extract the snapshot file path from the output
        snapshot_path = extract_snapshot_path(result.stdout)

        if result.returncode != 0:
            print("Error running the script:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            sys.exit(1)

        if snapshot_path:
            print(f"Snapshot captured: {snapshot_path}")
        else:
            print(
                "Warning: Snapshot may not have been captured."
                " Check if the specified line was executed."
            )
            print(result.stdout)
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file)
        except FileNotFoundError:
            pass  # File doesn't exist or has already been deleted


if __name__ == "__main__":
    main()
