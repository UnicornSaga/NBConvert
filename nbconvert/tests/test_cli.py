import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nbclient
import nbformat
import pytest
from click.testing import CliRunner

from nbconvert import cli
from nbconvert.cli import _is_float, _is_int, _resolve_type, nbconvert


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("True", True),
        ("False", False),
        ("None", None),
        ("12.51", 12.51),
        ("10", 10),
        ("hello world", "hello world"),
        ("😍", "😍"),
    ],
)
def test_resolve_type(test_input, expected):
    assert _resolve_type(test_input) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (13.71, True),
        ("False", False),
        ("None", False),
        (-8.2, True),
        (10, True),
        ("10", True),
        ("12.31", True),
        ("hello world", False),
        ("😍", False),
    ],
)
def test_is_float(value, expected):
    assert (_is_float(value)) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (13.71, True),
        ("False", False),
        ("None", False),
        (-8.2, True),
        ("-23.2", False),
        (10, True),
        ("13", True),
        ("hello world", False),
        ("😍", False),
    ],
)
def test_is_int(value, expected):
    assert (_is_int(value)) == expected


class TestCLI(unittest.TestCase):
    default_execute_kwargs = dict(
        input_path='input.ipynb',
        output_path='output.ipynb',
        parameters_specified=(),
        parameters={},
        engine_name=None,
        kernel_name=None,
        language=None,
        report_mode=False,
        cwd=None,
    )

    def setUp(self):
        self.runner = CliRunner()
        self.default_args = [
            self.default_execute_kwargs['input_path'],
            self.default_execute_kwargs['output_path'],
        ]
        self.sample_yaml_file = os.path.join(os.path.dirname(__file__), 'parameters', 'example.yaml')
        self.sample_json_file = os.path.join(os.path.dirname(__file__), 'parameters', 'example.json')

    def augment_execute_kwargs(self, **new_kwargs):
        kwargs = self.default_execute_kwargs.copy()
        kwargs.update(new_kwargs)
        return kwargs

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['-p', 'foo', 'bar', '--parameters', 'baz', '42'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(parameters={'foo': 'bar', 'baz': 42}))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters_raw(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['-r', 'foo', 'bar', '--parameters_raw', 'baz', '42'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(parameters={'foo': 'bar', 'baz': '42'}))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters_yaml(self, execute_patch):
        self.runner.invoke(
            nbconvert,
            self.default_args + ['-y', '{"foo": "bar"}', '--parameters_yaml', '{"foo2": ["baz"]}'],
        )
        execute_patch.assert_called_with(**self.augment_execute_kwargs(parameters={'foo': 'bar', 'foo2': ['baz']}))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters_yaml_date(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['-y', 'a_date: 2019-01-01'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(parameters={'a_date': '2019-01-01'}))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters_empty(self, execute_patch):
        # "#empty" ---base64--> "I2VtcHR5"
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_yaml = Path(tmpdir) / 'empty.yaml'
            empty_yaml.write_text('#empty')
            extra_args = [
                '--parameters_file',
                str(empty_yaml),
                '--parameters_yaml',
                '#empty',
                '--parameters_base64',
                'I2VtcHR5',
            ]
            self.runner.invoke(
                nbconvert,
                self.default_args + extra_args,
            )
            execute_patch.assert_called_with(
                **self.augment_execute_kwargs(
                    # should be empty
                    parameters={}
                )
            )

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters_yaml_override(self, execute_patch):
        self.runner.invoke(
            nbconvert,
            self.default_args + ['--parameters_yaml', '{"foo": "bar"}', '-y', '{"foo": ["baz"]}'],
        )
        execute_patch.assert_called_with(
            **self.augment_execute_kwargs(
                # Last input wins dict update
                parameters={'foo': ['baz']}
            )
        )

    @patch(f"{cli.__name__}.execute_notebook", side_effect=nbclient.exceptions.DeadKernelError("Fake"))
    def test_parameters_dead_kernel(self, execute_patch):
        result = self.runner.invoke(
            nbconvert,
            self.default_args + ['--parameters_yaml', '{"foo": "bar"}', '-y', '{"foo": ["baz"]}'],
        )
        assert result.exit_code == 138

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters_base64(self, execute_patch):
        extra_args = [
            '--parameters_base64',
            'eyJmb28iOiAicmVwbGFjZWQiLCAiYmFyIjogMn0=',
            '-b',
            'eydmb28nOiAxfQ==',
        ]
        self.runner.invoke(nbconvert, self.default_args + extra_args)
        execute_patch.assert_called_with(**self.augment_execute_kwargs(parameters={'foo': 1, 'bar': 2}))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_parameters_base64_date(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--parameters_base64', 'YV9kYXRlOiAyMDE5LTAxLTAx'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(parameters={'a_date': '2019-01-01'}))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_inject_input_path(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--inject-input-path'])
        execute_patch.assert_called_with(
            **self.augment_execute_kwargs(parameters={'NBCONVERT_INPUT_PATH': 'input.ipynb'})
        )

    @patch(f"{cli.__name__}.execute_notebook")
    def test_inject_output_path(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--inject-output-path'])
        execute_patch.assert_called_with(
            **self.augment_execute_kwargs(parameters={'NBCONVERT_OUTPUT_PATH': 'output.ipynb'})
        )

    @patch(f"{cli.__name__}.execute_notebook")
    def test_inject_paths(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--inject-paths'])
        execute_patch.assert_called_with(
            **self.augment_execute_kwargs(
                parameters={
                    'NBCONVERT_INPUT_PATH': 'input.ipynb',
                    'NBCONVERT_OUTPUT_PATH': 'output.ipynb',
                }
            )
        )

    @patch(f"{cli.__name__}.execute_notebook")
    def test_engine(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--engine', 'engine-that-could'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(engine_name='engine-that-could'))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_kernel(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['-k', 'python3'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(kernel_name='python3'))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_language(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['-l', 'python'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(language='python'))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_set_cwd(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--cwd', 'a/path/here'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(cwd='a/path/here'))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_log_level(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--log-level', 'WARNING'])
        # TODO: this does not actually test log-level being set
        execute_patch.assert_called_with(**self.augment_execute_kwargs())

    @patch(f"{cli.__name__}.execute_notebook")
    def test_report_mode(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--report-mode'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(report_mode=True))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_no_report_mode(self, execute_patch):
        self.runner.invoke(nbconvert, self.default_args + ['--no-report-mode'])
        execute_patch.assert_called_with(**self.augment_execute_kwargs(report_mode=False))

    @patch(f"{cli.__name__}.execute_notebook")
    def test_version(self, execute_patch):
        self.runner.invoke(nbconvert, ['--version'])
        execute_patch.assert_not_called()

    @patch(f"{cli.__name__}.execute_notebook")
    @patch(f"{cli.__name__}.display_notebook_help")
    def test_help_notebook(self, display_notebook_help, execute_path):
        self.runner.invoke(nbconvert, ['--help-notebook', 'input_path.ipynb'])
        execute_path.assert_not_called()
        assert display_notebook_help.call_count == 1
        assert display_notebook_help.call_args[0][1] == 'input_path.ipynb'

def nbconvert_cli(nbconvert_args=None, **kwargs):
    cmd = [sys.executable, '-m', 'nbconvert']
    if nbconvert_args:
        cmd.extend(nbconvert_args)
    return subprocess.Popen(cmd, **kwargs)


def nbconvert_version():
    try:
        proc = nbconvert_cli(['--version'], stdout=subprocess.PIPE)
        out, _ = proc.communicate()
        if proc.returncode:
            return None
        return out.decode('utf-8')
    except (OSError, SystemExit):  # pragma: no cover
        return None


@pytest.fixture()
def notebook():
    metadata = {'kernelspec': {'name': 'python3', 'language': 'python', 'display_name': 'python3'}}
    return nbformat.v4.new_notebook(
        metadata=metadata,
        cells=[nbformat.v4.new_markdown_cell('This is a notebook with kernel: python3')],
    )


require_nbconvert_installed = pytest.mark.skipif(not nbconvert_version(), reason='nbconvert is not installed')
