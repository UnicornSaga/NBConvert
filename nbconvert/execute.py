import ast
import os
from pathlib import Path
import uuid
import re

from autoimport import fix_code
import black
import isort
import nbformat

from nbconvert.exceptions import NBConvertExecutionError
from nbconvert.format import handle_missing_variables, find_files_containing_imports
from nbconvert.inspection import _infer_parameters
from nbconvert.iorw import get_pretty_path, load_notebook_node, local_file_io_cwd, write_ipynb, write_py
from nbconvert.log import logger
from nbconvert.parameterize import add_builtin_parameters, parameterize_notebook, parameterize_path


def execute_notebook(
    input_path,
    output_path,
    parameters_specified=None,
    parameters=None,
    engine_name=None,
    kernel_name=None,
    language=None,
    report_mode=False,
    cwd=None,
):
    """Executes a single notebook locally.

    Parameters
    ----------
    input_path : str or Path or nbformat.NotebookNode
        Path to input notebook or NotebookNode object of notebook
    output_path : str or Path or None
        Path to save executed notebook. If None, no file will be saved
    parameters_specified: tuple, optional
        The specified parameters for locating cells that needs to be converted
    parameters : dict, optional
        Arbitrary keyword arguments to pass to the notebook parameters
    engine_name : str, optional
        Name of execution engine to use
    kernel_name : str, optional
        Name of kernel to execute the notebook against
    language : str, optional
        Programming language of the notebook
    report_mode : bool, optional
        Flag for whether or not to hide input.
    cwd : str or Path, optional
        Working directory to use when executing the notebook

    Returns
    -------
    nb : NotebookNode
       Executed notebook object
    """
    if isinstance(input_path, Path):
        input_path = str(input_path)
    if isinstance(output_path, Path):
        output_path = str(output_path)
    if isinstance(cwd, Path):
        cwd = str(cwd)

    path_parameters = add_builtin_parameters(parameters)
    input_path = parameterize_path(input_path, path_parameters)
    output_path = parameterize_path(output_path, path_parameters)

    logger.info(f"Input Notebook:  {get_pretty_path(input_path)}")
    logger.info(f"Output Path: {get_pretty_path(output_path)}")
    with local_file_io_cwd():
        if cwd is not None:
            logger.info(f"Working directory: {get_pretty_path(cwd)}")

        nb = load_notebook_node(input_path)

        # Parameterize the Notebook.
        if parameters:
            parameter_predefined = _infer_parameters(nb, name=kernel_name, language=language)
            parameter_predefined = {p.name for p in parameter_predefined}
            for p in parameters:
                if p not in parameter_predefined:
                    logger.warning(f"Passed unknown parameter: {p}")
            nb = parameterize_notebook(
                nb,
                parameters,
                report_mode,
                kernel_name=kernel_name,
                language=language,
                engine_name=engine_name,
            )

        nb = prepare_notebook_metadata(nb, input_path, output_path, report_mode)
        nb = remove_error_markers(nb)

        # Write tagged cell into separated python files
        version_uuid = uuid.uuid4()
        cell_buffers = prepare_notebook_cell(nb, parameters_specified)
        for cell_tag, cell_content in cell_buffers.items():
            fix_import_buffer = fix_code(cell_content)
            sorted_import_buffer = isort.code(fix_import_buffer)
            cell_content = handle_missing_variables(cell_tag, sorted_import_buffer)
            cell_content = black.format_str(
                cell_content,
                mode=black.Mode(
                    target_versions={black.TargetVersion.PY38},
                    string_normalization=True,
                    is_pyi=False,
                ),
            )
            write_py(cell_content, f"{output_path}/{version_uuid}/{cell_tag}.py")

            current_root_dir = os.environ.get('ROOT_PROJECT_DIR', None)
            if not current_root_dir:
                logger.info("Missing env ROOT_PROJECT_DIR")
            missing_import_files = find_files_containing_imports(cell_content, current_root_dir)
            for file_path in missing_import_files:
                file_name = str(file_path).split('/')[-1]
                with open(file_path, 'r') as f:
                    file_content = f.read()
                    write_py(file_content, f"{output_path}/{version_uuid}/{file_name}")

        logger.info(f"Generated Python artifacts with UUID directory {version_uuid}")

        return version_uuid


def _prepare_code_buffer(code_buffer):
    pattern = re.compile(r'\bdef\b\s+\w+\s*\(\[^\)]*\):\s*\(\[^]*?\)\(?=\s*\bdef\b|\s*$\)', re.DOTALL)
    match = pattern.search(code_buffer)

    if match:
        return match.group(1).strip()
    else:
        return code_buffer


def prepare_notebook_cell(nb, parameters):
    BUFFER = {}
    for cell in nb.cells:
        if cell.cell_type == 'code':
            for tag in cell.metadata.tags:
                if tag in parameters:
                    if tag not in BUFFER:
                        BUFFER[tag] = f"def {tag}():"
                    cell_source = '\n' + cell.source
                    cell_source = cell_source.replace('\n', '\n\t')
                    BUFFER[tag] += cell_source + '\n'

    return BUFFER


def prepare_notebook_metadata(nb, input_path, output_path, report_mode=False):
    """Prepare metadata associated with a notebook and its cells

    Parameters
    ----------
    nb : NotebookNode
       Executable notebook object
    input_path : str
        Path to input notebook
    output_path : str
       Path to write executed notebook
    report_mode : bool, optional
       Flag to set report mode
    """
    # Hide input if report-mode is set to True.
    if report_mode:
        for cell in nb.cells:
            if cell.cell_type == 'code':
                cell.metadata['jupyter'] = cell.get('jupyter', {})
                cell.metadata['jupyter']['source_hidden'] = True

    # Record specified environment variable values.
    nb.metadata.nbconvert['input_path'] = input_path
    nb.metadata.nbconvert['output_path'] = output_path

    return nb


ERROR_MARKER_TAG = "nbconvert-error-cell-tag"

ERROR_STYLE = 'style="color:red; font-family:Helvetica Neue, Helvetica, Arial, sans-serif; font-size:2em;"'

ERROR_MESSAGE_TEMPLATE = (
    f"<span {ERROR_STYLE}>An Exception was encountered at '<a href=\"#nbconvert-error-cell\">In [%s]</a>'.</span>"
)

ERROR_ANCHOR_MSG = (
    f'<span id="nbconvert-error-cell" {ERROR_STYLE}>'
    'Execution using nbconvert encountered an exception here and stopped:'
    '</span>'
)


def remove_error_markers(nb):
    nb.cells = [cell for cell in nb.cells if ERROR_MARKER_TAG not in cell.metadata.get("tags", [])]
    return nb


def raise_for_execution_errors(nb, output_path):
    """Assigned parameters into the appropriate place in the input notebook

    Parameters
    ----------
    nb : NotebookNode
       Executable notebook object
    output_path : str
       Path to write executed notebook
    """
    error = None
    for index, cell in enumerate(nb.cells):
        if cell.get("outputs") is None:
            continue

        for output in cell.outputs:
            if output.output_type == "error":
                if output.ename == "SystemExit" and (output.evalue == "" or output.evalue == "0"):
                    continue
                error = NBConvertExecutionError(
                    cell_index=index,
                    exec_count=cell.execution_count,
                    source=cell.source,
                    ename=output.ename,
                    evalue=output.evalue,
                    traceback=output.traceback,
                )
                break

    if error:
        # Write notebook back out with the Error Message at the top of the Notebook, and a link to
        # the relevant cell (by adding a note just before the failure with an HTML anchor)
        error_msg = ERROR_MESSAGE_TEMPLATE % str(error.exec_count)
        error_msg_cell = nbformat.v4.new_markdown_cell(error_msg)
        error_msg_cell.metadata['tags'] = [ERROR_MARKER_TAG]
        error_anchor_cell = nbformat.v4.new_markdown_cell(ERROR_ANCHOR_MSG)
        error_anchor_cell.metadata['tags'] = [ERROR_MARKER_TAG]

        # Upgrade the Notebook to the latest v4 before writing into it
        nb = nbformat.v4.upgrade(nb)

        # put the anchor before the cell with the error, before all the indices change due to the
        # heading-prepending
        nb.cells.insert(error.cell_index, error_anchor_cell)
        nb.cells.insert(0, error_msg_cell)

        write_ipynb(nb, output_path)
        raise error
