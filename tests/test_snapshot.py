import pytest
import os
import tempfile
import pickle
import sys
import io
from unittest.mock import patch, MagicMock

# Import the snapshot debugger module
# Assuming the main module is named snapshot.py with create_snapshot_cli as the main function
from ctxclip import snapshot


@pytest.fixture
def test_environment():
    """Create a temporary test environment with a Python file"""
    # Create a temporary directory for test snapshots
    test_dir = tempfile.mkdtemp()
    test_file = os.path.join(test_dir, "test_script.py")

    # Create a simple test Python file
    with open(test_file, "w") as f:
        f.write(
            """
def example_function(a, b):
    x = a + b
    y = a * b
    return x + y

if __name__ == "__main__":
    result = example_function(5, 10)
    print(f"Result: {result}")
"""
        )

    yield {"test_dir": test_dir, "test_file": test_file}

    # Clean up temporary files
    if os.path.exists(test_file):
        os.unlink(test_file)
    if os.path.exists(test_dir):
        os.rmdir(test_dir)


def test_inject_snapshot_code(test_environment):
    """Test that snapshot code is properly injected into a file"""
    test_file = test_environment["test_file"]
    test_dir = test_environment["test_dir"]

    temp_file = snapshot.inject_snapshot_code(
        test_file, line_num=3, label="test_snapshot", output_dir=test_dir
    )

    # Verify the file was created
    assert os.path.exists(temp_file)

    # Read the content and verify the snapshot call was injected
    with open(temp_file, "r") as f:
        content = f.read()

    # Check that the debugger code was injected
    assert "class DebugSnapshot:" in content

    # Check that the snapshot call was injected at the right line
    lines = content.split("\n")
    snapshot_line_found = False
    for line in lines:
        if '_snapshot_debugger.capture("test_snapshot")' in line:
            snapshot_line_found = True
            break

    assert snapshot_line_found

    # Clean up
    os.unlink(temp_file)


def test_extract_snapshot_path():
    """Test that snapshot path is correctly extracted from output"""
    test_output = (
        "Some output\nDEBUG_SNAPSHOT_PATH: /path/to/snapshot.snapshot\nMore output"
    )
    path = snapshot.extract_snapshot_path(test_output)
    assert path == "/path/to/snapshot.snapshot"

    # Test with no match
    no_match_output = "Some output without a snapshot path"
    path = snapshot.extract_snapshot_path(no_match_output)
    assert path is None


@patch("subprocess.run")
def test_create_snapshot_cli(mock_run, test_environment, monkeypatch, capsys):
    """Test the main CLI function"""
    test_file = test_environment["test_file"]
    test_dir = test_environment["test_dir"]

    # Setup mocks
    mock_temp_file = os.path.join(test_dir, "temp_script.py")
    
    with patch("ctxclip.snapshot.inject_snapshot_code") as mock_inject:
        mock_inject.return_value = mock_temp_file

        mock_process = MagicMock()
        mock_process.stdout = "DEBUG_SNAPSHOT_PATH: /path/to/snapshot.snapshot"
        mock_process.returncode = 0
        mock_run.return_value = mock_process

        # Mock command line arguments
        test_args = [
            "snapshot.py",
            "--file",
            test_file,
            "--line-num",
            "3",
            "--label",
            "test_cli",
            "--output-dir",
            test_dir,
        ]
        monkeypatch.setattr("sys.argv", test_args)

        # Call the function with mocked command line arguments
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            args = MagicMock()
            args.file = test_file
            args.line_num = 3
            args.label = "test_cli"
            args.output_dir = test_dir
            args.args = []
            mock_parse_args.return_value = args

            try:
                snapshot.create_snapshot_cli()
            except SystemExit:
                pass  # Expected in some cases

        # Verify the function was called with correct arguments
        mock_inject.assert_called_once_with(test_file, 3, "test_cli", test_dir)

        # Verify subprocess.run was called
        mock_run.assert_called_once()

        # Check output contains the snapshot path
        captured = capsys.readouterr()
        assert "Snapshot captured" in captured.out


def test_filter_picklable(test_environment):
    """Test the _filter_picklable method of DebugSnapshot class"""
    test_file = test_environment["test_file"]
    test_dir = test_environment["test_dir"]

    # Create a temporary file with the snapshot debugger code
    temp_file = snapshot.inject_snapshot_code(
        test_file, line_num=3, output_dir=test_dir
    )

    # Import the temporary file to access the DebugSnapshot class
    sys.path.append(os.path.dirname(temp_file))
    temp_module_name = os.path.basename(temp_file).replace(".py", "")

    # Use importlib to import the module
    import importlib.util

    spec = importlib.util.spec_from_file_location(temp_module_name, temp_file)
    temp_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(temp_module)

    # Create a DebugSnapshot instance
    debugger = temp_module._snapshot_debugger

    # Test with picklable and non-picklable objects
    test_dict = {
        "number": 42,
        "string": "hello",
        "list": [1, 2, 3],
        "unpicklable": lambda x: x,  # Functions are not picklable
    }

    filtered = debugger._filter_picklable(test_dict)

    # Check that picklable objects are preserved
    assert filtered["number"] == 42
    assert filtered["string"] == "hello"
    assert filtered["list"] == [1, 2, 3]

    # Check that non-picklable objects are replaced with a string
    assert isinstance(filtered["unpicklable"], str)
    assert "Unpicklable object" in filtered["unpicklable"]

    # Clean up
    os.unlink(temp_file)
    sys.path.remove(os.path.dirname(temp_file))


def test_line_number_out_of_range(test_environment):
    """Test handling of line numbers that exceed file length"""
    test_file = test_environment["test_file"]
    test_dir = test_environment["test_dir"]

    # Get the number of lines in the test file
    with open(test_file, "r") as f:
        num_lines = len(f.readlines())

    # Try to inject at a line number beyond the end of the file
    temp_file = snapshot.inject_snapshot_code(
        test_file, line_num=num_lines + 10, output_dir=test_dir  # Way beyond the end
    )

    # Read the content
    with open(temp_file, "r") as f:
        content = f.read()

    # The snapshot call should be added at the end
    lines = content.split("\n")
    last_code_line = [line for line in lines if "_snapshot_debugger.capture" in line][
        -1
    ]
    assert last_code_line  # Should find the line

    # Clean up
    os.unlink(temp_file)


def test_file_not_found():
    """Test handling of non-existent files"""
    with patch(
        "sys.argv", ["snapshot.py", "--file", "/nonexistent/file.py", "--line-num", "1"]
    ):
        with pytest.raises(SystemExit):
            snapshot.create_snapshot_cli()


def test_subprocess_error(test_environment, monkeypatch):
    """Test handling of subprocess errors"""
    test_file = test_environment["test_file"]

    with patch("ctxclip.snapshot.inject_snapshot_code") as mock_inject:
        mock_inject.return_value = "temp_file.py"

        with patch("subprocess.run") as mock_run:
            # Simulate a failed subprocess
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.stdout = "Error in script execution"
            mock_run.return_value = mock_process

            # Mock command line arguments
            monkeypatch.setattr(
                "sys.argv", ["snapshot.py", "--file", test_file, "--line-num", "3"]
            )

            with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
                args = MagicMock()
                args.file = test_file
                args.line_num = 3
                args.label = 'foo'
                args.output_dir = "debug_snapshots"
                args.args = []
                mock_parse_args.return_value = args

                with pytest.raises(SystemExit):
                    # import ipdb; ipdb.set_trace()
                    snapshot.create_snapshot_cli()
