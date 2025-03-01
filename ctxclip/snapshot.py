"""snapshot debugger"""

import inspect
import traceback
import pickle
import os
import datetime
import argparse
import sys
import tempfile
import subprocess
import re


class DebugSnapshot:
    """a non-interrupting debug snapshot"""

    def __init__(self, snapshot_dir="debug_snapshots"):
        self.snapshot_dir = snapshot_dir
        if not os.path.exists(snapshot_dir):
            os.makedirs(snapshot_dir)

    def capture(self, label=None):
        """Capture the current state including local/global variables and call stack"""
        # Get the frame of the caller
        frame = inspect.currentframe().f_back

        # Generate timestamp and filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}"
        if label:
            filename += f"_{label}"
        filename += ".snapshot"
        filepath = os.path.join(self.snapshot_dir, filename)

        # Capture stack trace
        stack_trace = traceback.format_stack()

        # Capture local and global variables
        locals_copy = frame.f_locals.copy()
        globals_copy = frame.f_globals.copy()

        # Filter out non-picklable objects
        filtered_locals = self._filter_picklable(locals_copy)
        filtered_globals = self._filter_picklable(globals_copy)

        # Create snapshot data
        snapshot_data = {
            "timestamp": timestamp,
            "label": label,
            "stack_trace": stack_trace,
            "locals": filtered_locals,
            "globals": filtered_globals,
            "filename": frame.f_code.co_filename,
            "lineno": frame.f_lineno,
            "function": frame.f_code.co_name,
        }

        # Save snapshot
        with open(filepath, "wb") as f:
            pickle.dump(snapshot_data, f)

        print(f"Debug snapshot saved to {filepath}")
        return filepath, snapshot_data

    def _filter_picklable(self, data_dict):
        """Filter out objects that can't be pickled"""
        filtered = {}
        for key, value in data_dict.items():
            try:
                # Test if object is picklable
                pickle.dumps(value)
                filtered[key] = value
            except pickle.PicklingError:
                filtered[key] = f"<Unpicklable object of type {type(value).__name__}>"
        return filtered

    @staticmethod
    def load(filepath):
        """Load a snapshot from file"""
        with open(filepath, "rb") as f:
            snapshot_data = pickle.load(f)
        return snapshot_data

    @staticmethod
    def print_snapshot(snapshot_data):
        """Print the contents of a snapshot in a readable format"""
        fname = snapshot_data["filename"]
        lineno = snapshot_data["lineno"]
        function = snapshot_data["function"]
        print("\n" + "=" * 50)
        print(f"Debug Snapshot: {snapshot_data.get('label', 'Unnamed')}")
        print(f"Captured at: {snapshot_data['timestamp']}")
        print(f"Location: {fname}:{lineno} in {function}")

        print("\nCall Stack:")
        for line in snapshot_data["stack_trace"]:
            print(f"  {line.strip()}")

        print("\nLocal Variables:")
        for key, value in snapshot_data["locals"].items():
            print(f"  {key} = {value}")

        print("\nGlobal Variables (selected):")
        # Print only a subset of globals to avoid overwhelming output
        for key, value in list(snapshot_data["globals"].items())[:20]:
            if not key.startswith("__"):
                print(f"  {key} = {value}")
        print("=" * 50)


# Create a singleton instance for easy import and use
snapshot_debugger = DebugSnapshot()


def create_snapshot_cli():
    """create snapshot cli"""
    # TODO use pattern from other modules
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
            return snapshot_path
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


def inject_snapshot_code(file_path, line_num, label=None, output_dir="debug_snapshots"):
    """injects the snapshot code to file_path:line_num"""
    # TODO we can make this cleaner by isolating the full debugsnapshot source in it's own file
    debugger_code = "\n\n".join(
        [
            "\n".join(
                [
                    "import inspect",
                    "import traceback",
                    "import pickle",
                    "import os",
                    "import datetime",
                    "import sys",
                ]
            ),
            inspect.getsource(DebugSnapshot),
            f"_snapshot_debugger = DebugSnapshot('{output_dir}');",
        ]
    )
    # Read the original file
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

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
        label_str = f'"{label}"' if label else "None"
        snapshot_line = f"{indentation}_snapshot_debugger.capture({label_str})  # Injected snapshot call\n"

        if line_num <= len(lines):
            lines.insert(line_num, snapshot_line)
        else:
            lines.append(snapshot_line)
    else:
        # Handle invalid line numbers
        print(
            f"Warning: Line number {line_num} is out of range. Adding snapshot at the end."
        )
        lines.append(
            f"_snapshot_debugger.capture({label_str if 'label_str' in locals() else 'None'})  # Injected snapshot call\n"
        )

    # Create a temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".py", prefix="_snapshot_")
    os.close(temp_fd)

    # Combine the debugger code with the modified content
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(debugger_code + "\n" + "".join(lines))

    return temp_path


def extract_snapshot_path(output):
    """Extract the snapshot file path from the output"""
    match = re.search(r"DEBUG_SNAPSHOT_PATH: (.+)$", output, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


if __name__ == "__main__":
    create_snapshot_cli()
