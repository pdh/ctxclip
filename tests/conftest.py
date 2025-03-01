"""conftest"""

import os
import tempfile
import shutil
import pytest

SAMPLE_CODE = """
def sample_function(x):
    return x * 2

class SampleClass:
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        return self.value
        
sample_variable = 42

def using_function():
    result = sample_function(10)
    obj = SampleClass(result)
    return obj.get_value() + sample_variable
"""


@pytest.fixture
def sample_file():
    """Create a temporary file with sample code for testing."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(SAMPLE_CODE.encode("utf-8"))
        file_path = f.name

    yield file_path

    # Cleanup after tests
    os.unlink(file_path)


@pytest.fixture
def multi_file_package():
    """Create a temporary package with multiple Python files for testing."""
    # Create a temporary directory
    package_dir = tempfile.mkdtemp()

    # Create main.py
    main_content = """
from utils import helper_function
from models import DataModel

def main_function():
    model = DataModel("test")
    result = helper_function(model)
    return result
"""
    with open(os.path.join(package_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(main_content)

    # Create utils.py
    utils_content = """
def helper_function(data):
    return process_data(data)
    
def process_data(data):
    return data.get_value() * 2
"""
    with open(os.path.join(package_dir, "utils.py"), "w", encoding="utf-8") as f:
        f.write(utils_content)

    # Create models.py
    models_content = """
class DataModel:
    def __init__(self, value):
        self.value = value
        
    def get_value(self):
        return len(self.value)
"""
    with open(os.path.join(package_dir, "models.py"), "w", encoding="utf-8") as f:
        f.write(models_content)

    yield package_dir

    # Cleanup
    shutil.rmtree(package_dir)
