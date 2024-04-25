import os
import unittest

from nbconvert.execute import prepare_notebook_cell
from nbconvert.format import (
    handle_missing_variables,
    find_files_containing_imports
)
from nbconvert.iorw import load_notebook_node
from nbconvert.tests import get_notebook_path


class TestHandleMissingVariables(unittest.TestCase):
    def setUp(self):
        self.notebook_name = 'simple_execution.ipynb'
        self.notebook_path = get_notebook_path(self.notebook_name)
        self.nb = load_notebook_node(self.notebook_path)

    def test_handle_variable(self):
        buffer = prepare_notebook_cell(self.nb, ['valid_variable'])
        code_content = ""
        for _, cell_content in buffer.items():
            code_content += cell_content

        code_content = handle_missing_variables(code_content)
        assert code_content == 'def valid_variable():\n\tx = 0\n\tfor i in range(10):\n\t    x += i\n\t\n\tprint(x)\n'

    def test_handle_missing_variable(self):
        buffer = prepare_notebook_cell(self.nb, ['invalid_variable'])
        code_content = ""
        for _, cell_content in buffer.items():
            code_content += cell_content

        code_content = handle_missing_variables(code_content)
        assert code_content == 'def invalid_variable():\n\tfor i in range(10):\n\t    x += i\n\t\n\tprint(x)\n'

    def test_handle_complex_variable(self):
        buffer = prepare_notebook_cell(self.nb, ['complex_variable'])
        code_content = ""
        for _, cell_content in buffer.items():
            code_content += cell_content

        code_content = handle_missing_variables(code_content)
        print({"loz": code_content})
        assert code_content == "def complex_variable():\n\tfor (a, b) in range(10):\n\t    print(a, b)\n\t\n\ti = 0\n\twhile i < 10:\n\t    i += 1\n\t\n\twith open('utils.py') as f:\n\t    f.read()\n"


class TestFindMissingImports(unittest.TestCase):
    def setUp(self):
        self.notebook_name = 'simple_execution.ipynb'
        self.notebook_path = get_notebook_path(self.notebook_name)
        self.nb = load_notebook_node(self.notebook_path)
        self.cwd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'notebooks')

    def test_no_missing_imports(self):
        buffer = prepare_notebook_cell(self.nb, ['valid_variable'])
        code_content = ""
        for _, cell_content in buffer.items():
            code_content += cell_content

        missing_imports_path = find_files_containing_imports(code_content, self.cwd)

        assert missing_imports_path == set()

    def test_has_missing_imports(self):
        buffer = prepare_notebook_cell(self.nb, ['missing_import'])
        code_content = ""
        for _, cell_content in buffer.items():
            code_content += cell_content

        missing_imports_path = find_files_containing_imports(code_content, self.cwd)
        assert missing_imports_path == {self.cwd + '/utils.py'}
