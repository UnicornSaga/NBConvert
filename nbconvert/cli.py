import base64
import os
import platform
import sys
import traceback
from stat import S_ISFIFO

import click
import nbclient
import yaml

from nbconvert.execute import execute_notebook
from nbconvert.log import logger
from nbconvert.inspection import display_notebook_help
from nbconvert.iorw import NoDatesSafeLoader, read_yaml_file
from nbconvert.version import version

click.disable_unicode_literals_warning = True

INPUT_PIPED = S_ISFIFO(os.fstat(0).st_mode)
OUTPUT_PIPED = not sys.stdout.isatty()


def print_nbconvert_version(ctx, param, value):
    if not value:
        return
    print(f"{version} from {__file__} ({platform.python_version()})")
    ctx.exit()


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.pass_context
@click.argument('notebook_path', required=not INPUT_PIPED)
@click.argument('output_path', default="")
@click.option(
    '--output-path',
    default="./artifacts",
    help="Output file destination",
)
@click.option(
    '--help-notebook',
    is_flag=True,
    default=False,
    help='Display parameters information for the given notebook path.',
)
@click.option("--parameter_specified", '-P', multiple=True, help='Parameters to look for in the notebook.')
@click.option('--parameters', '-p', nargs=2, multiple=True, help='Parameters to pass to the parameters cell.')
@click.option('--parameters_raw', '-r', nargs=2, multiple=True, help='Parameters to be read as raw string.')
@click.option('--parameters_file', '-f', multiple=True, help='Path to YAML file containing parameters.')
@click.option('--parameters_yaml', '-y', multiple=True, help='YAML string to be used as parameters.')
@click.option('--parameters_base64', '-b', multiple=True, help='Base64 encoded YAML string as parameters.')
@click.option(
    '--inject-input-path',
    is_flag=True,
    default=False,
    help="Insert the path of the input notebook as NBCONVERT_INPUT_PATH as a notebook parameter.",
)
@click.option(
    '--inject-output-path',
    is_flag=True,
    default=False,
    help="Insert the path of the output notebook as NBCONVERT_OUTPUT_PATH as a notebook parameter.",
)
@click.option(
    '--inject-paths',
    is_flag=True,
    default=False,
    help=(
        "Insert the paths of input/output notebooks as NBCONVERT_INPUT_PATH/NBCONVERT_OUTPUT_PATH"
        " as notebook parameters."
    ),
)
@click.option('--engine', help='The execution engine name to use in evaluating the notebook.')
@click.option(
    '--kernel',
    '-k',
    help='Name of kernel to run. Ignores kernel name in the notebook document metadata.',
)
@click.option(
    '--language',
    '-l',
    help='Language for notebook execution. Ignores language in the notebook document metadata.',
)
@click.option('--cwd', default=None, help='Working directory to run notebook in.')
@click.option(
    '--log-level',
    type=click.Choice(['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
    default='INFO',
    help='Set log level',
)
@click.option('--report-mode/--no-report-mode', default=False, help="Flag for hiding input.")
@click.option(
    '--version',
    is_flag=True,
    callback=print_nbconvert_version,
    expose_value=False,
    is_eager=True,
    help='Flag for displaying the version.',
)
def nbconvert(
    click_ctx,
    notebook_path,
    output_path,
    help_notebook,
    parameter_specified,
    parameters,
    parameters_raw,
    parameters_file,
    parameters_yaml,
    parameters_base64,
    inject_input_path,
    inject_output_path,
    inject_paths,
    engine,
    kernel,
    language,
    cwd,
    log_level,
    report_mode,
):
    """This utility executes a single notebook in a subprocess.

    NBConvert takes a source notebook, applies the notebook with parameters for validation,
    executes the notebook with the specified kernel,
    saves the output in the destination notebook and split the specified cells to machine learning production code.

    The NOTEBOOK_PATH and OUTPUT_PATH can now be replaced by `-` representing
    stdout and stderr, or by the presence of pipe inputs / outputs.
    Meaning that

    `<generate input>... | nbconvert | ...<process output>`

    with `nbconvert - -` being implied by the pipes will read a notebook
    from stdin and write it out to stdout.

    """
    # Jupyter deps use frozen modules, so we disable the python 3.11+ warning about debugger if running the CLI
    if 'PYDEVD_DISABLE_FILE_VALIDATION' not in os.environ:
        os.environ['PYDEVD_DISABLE_FILE_VALIDATION'] = '1'

    if not help_notebook:
        required_output_path = not (INPUT_PIPED or OUTPUT_PIPED)
        if required_output_path and not output_path:
            raise click.UsageError("Missing argument 'OUTPUT_PATH'")

    if INPUT_PIPED and notebook_path and not output_path:
        input_path = '-'
        output_path = notebook_path
    else:
        input_path = notebook_path or '-'
        output_path = output_path or '-'

    if output_path == '-':
        # Save notebook to stdout just once
        request_save_on_cell_execute = False

        # Reduce default log level if we pipe to stdout
        if log_level == 'INFO':
            log_level = 'ERROR'

    logger.setLevel(level=log_level)

    # Read in Parameters
    parameters_final = {}
    if inject_input_path or inject_paths:
        parameters_final['NBCONVERT_INPUT_PATH'] = input_path
    if inject_output_path or inject_paths:
        parameters_final['NBCONVERT_OUTPUT_PATH'] = output_path
    for params in parameters_base64 or []:
        parameters_final.update(yaml.load(base64.b64decode(params), Loader=NoDatesSafeLoader) or {})
    for files in parameters_file or []:
        parameters_final.update(read_yaml_file(files) or {})
    for params in parameters_yaml or []:
        parameters_final.update(yaml.load(params, Loader=NoDatesSafeLoader) or {})
    for name, value in parameters or []:
        parameters_final[name] = _resolve_type(value)
    for name, value in parameters_raw or []:
        parameters_final[name] = value

    if help_notebook:
        sys.exit(display_notebook_help(click_ctx, notebook_path, parameters_final))

    try:
        execute_notebook(
            input_path=input_path,
            output_path=output_path,
            parameters_specified=parameter_specified,
            parameters=parameters_final,
            engine_name=engine,
            kernel_name=kernel,
            language=language,
            report_mode=report_mode,
            cwd=cwd,
        )
    except nbclient.exceptions.DeadKernelError:
        # Exiting with a special exit code for dead kernels
        traceback.print_exc()
        sys.exit(138)


def _resolve_type(value):
    if value == "True":
        return True
    elif value == "False":
        return False
    elif value == "None":
        return None
    elif _is_int(value):
        return int(value)
    elif _is_float(value):
        return float(value)
    else:
        return value


def _is_int(value):
    """Use casting to check if value can convert to an `int`."""
    try:
        int(value)
    except ValueError:
        return False
    else:
        return True


def _is_float(value):
    """Use casting to check if value can convert to a `float`."""
    try:
        float(value)
    except ValueError:
        return False
    else:
        return True
