import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call

import pytest
from nbformat.v4 import new_code_cell, new_notebook

from nbconvert.exceptions import NBConvertParameterOverwriteWarning
from nbconvert.iorw import load_notebook_node
from nbconvert.utils import (
    any_tagged_cell,
    chdir,
    merge_kwargs,
    remove_args,
    retry,
    nb_kernel_name,
    nb_language,
    find_first_tagged_cell_index,
)
from nbconvert.tests import get_notebook_path


class TestUtils(unittest.TestCase):
    def test_no_tagged_cell(self):
        nb = new_notebook(
            cells=[new_code_cell('a = 2', metadata={"tags": []})],
        )
        assert not any_tagged_cell(nb, "parameters")

    def test_tagged_cell(self):
        nb = new_notebook(
            cells=[new_code_cell('a = 2', metadata={"tags": ["parameters"]})],
        )
        assert any_tagged_cell(nb, "parameters")

    def test_merge_kwargs(self):
        with warnings.catch_warnings(record=True) as wrn:
            assert merge_kwargs({"a": 1, "b": 2}, a=3) == {"a": 3, "b": 2}
            assert len(wrn) == 1
            assert issubclass(wrn[0].category, NBConvertParameterOverwriteWarning)
            assert wrn[0].message.__str__() == "Callee will overwrite caller's argument(s): a=3"

    def test_remove_args(self):
        assert remove_args(["a"], a=1, b=2, c=3) == {"c": 3, "b": 2}

    def test_retry(self):
        m = Mock(side_effect=RuntimeError(), __name__="m", __module__="test_s3", __doc__="m")
        wrapped_m = retry(3)(m)
        with pytest.raises(RuntimeError):
            wrapped_m("foo")
        m.assert_has_calls([call("foo"), call("foo"), call("foo")])

    def test_chdir(self):
        old_cwd = Path.cwd()
        with TemporaryDirectory() as temp_dir:
            with chdir(temp_dir):
                assert Path.cwd() != old_cwd

        assert Path.cwd() == old_cwd

    def test_nb_has_kernel_name(self):
        notebook_name = 'simple_execute.ipynb'
        notebook_path = get_notebook_path(notebook_name)
        nb = load_notebook_node(notebook_path)

        kernel_name = nb_kernel_name(nb)

        assert kernel_name == 'python3'

    def test_nb_language(self):
        notebook_name = 'simple_execute.ipynb'
        notebook_path = get_notebook_path(notebook_name)
        nb = load_notebook_node(notebook_path)

        language = nb_language(nb)

        assert language == 'python'

    def test_find_first_tagged_cell_index_fail(self):
        notebook_name = 'simple_execute.ipynb'
        notebook_path = get_notebook_path(notebook_name)
        nb = load_notebook_node(notebook_path)

        tagged_cell = find_first_tagged_cell_index(nb, 'tag')

        assert tagged_cell == -1

    def test_find_first_tagged_cell_index_success(self):
        notebook_name = 'simple_execute.ipynb'
        notebook_path = get_notebook_path(notebook_name)
        nb = load_notebook_node(notebook_path)

        tagged_cell = find_first_tagged_cell_index(nb, 'parameters')

        assert tagged_cell == 0
