"""snapshot debugger"""
import os
import inspect
import traceback
import datetime
import pickle

class DebugSnapshot:
    """a non-interrupting debug snapshot"""

    def __init__(self, snapshot_dir="debug_snapshots"):
        self.snapshot_dir = snapshot_dir
        if not os.path.exists(snapshot_dir):
            os.makedirs(snapshot_dir)

    def capture(self, label=None):
        """Capture the current state including local/global variables and call stack"""
        # Get the frame of the caller
        current_frame = inspect.currentframe()
        if not current_frame:
            raise ValueError("no current frame")

        frame = current_frame.f_back
        if not frame:
            raise AttributeError("f_back not found")

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
            except AttributeError:
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
