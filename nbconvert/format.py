import ast
import os

from nbconvert.log import logger


def handle_missing_variables(cell_tag, code_buffer):
    undefined_variables = set()
    function_parameters = set()
    user_defined_function = set()
    imports = set()

    def _visit_node_for_undefined_variables(node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            variable_name = node.id

            # Check if the variable is not defined locally and is not a function parameter
            if variable_name not in function_parameters and \
                    variable_name not in __builtins__ and \
                    variable_name not in user_defined_function and \
                    variable_name not in imports:
                logger.info(f"Undefined variable of parameter {cell_tag}: {variable_name}")
                undefined_variables.add(variable_name)


    def _visit_node_for_function_parameters(node):
        if isinstance(node, ast.FunctionDef):
            user_defined_function.add(node.name)
            for arg in node.args.args:
                function_parameters.add(arg.arg)


    def _visit_node_for_imports(node):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.name)
            module = node.module
            if module:
                imports.add(module)


    try:
        buffer_tree = ast.parse(code_buffer)

        # First, visit the tree to collect function parameters
        for node in ast.walk(buffer_tree):
            _visit_node_for_function_parameters(node)

        for node in ast.walk(buffer_tree):
            _visit_node_for_imports(node)
        # Then, visit the tree again to collect undefined variables
        for node in ast.walk(buffer_tree):
            _visit_node_for_undefined_variables(node)

        if len(undefined_variables) != 0:
            new_code_buffer = "\n".join(f"{var} = None" for var in undefined_variables) + "\n\n" + code_buffer
            return new_code_buffer
        else:
            return code_buffer
    except SyntaxError as e:
        raise SyntaxError(f"Syntax error in code: {e}")

def _extract_imports(code):
    imports = []

    def visit_node(node):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            sub_module = []
            for alias in node.names:
                sub_module.append(alias.name)
            module = node.module
            if module:
                imports.append({module : sub_module})

    tree = ast.parse(code)
    for node in ast.walk(tree):
        visit_node(node)

    return imports


def _find_missing_imports(code):
    missing_imports = []

    dependencies = _extract_imports(code)

    for dependency in dependencies:
        try:
            if isinstance(dependency, dict):
                sub_module = list(dependency.keys())[0]
                for sub in dependency[sub_module]:
                    __import__(f"{sub_module}.{sub}")
            else:
                __import__(dependency)
        except ImportError:
            # If the import fails, add it to the list of missing imports
            missing_imports.append(dependency)

    # Now you have a set of missing imports
    return missing_imports


def find_files_containing_imports(code, project_directory):
    matching_files = set()
    visited_files = set()

    def search_files(code_buffer, curr_file):
        if curr_file in visited_files or \
            'venv' in curr_file or \
                curr_file.split('.')[-1] != 'py':
            return

        visited_files.add(curr_file)
        missing_imports = _find_missing_imports(code_buffer)
        with open(curr_file, 'r') as f:
            file_content = f.read()
            for missing_import in missing_imports:
                if isinstance(missing_import, dict):
                    sub_module = list(missing_import.keys())[0]
                    for func in missing_import[sub_module]:
                        if sub_module in curr_file and func in file_content:
                            matching_files.add(curr_file)
                else:
                    if missing_import in curr_file:
                        matching_files.add(curr_file)

                next_curr_dir = os.path.dirname(curr_file)
                search_files(file_content, next_curr_dir)

    for root, dirs, files in os.walk(project_directory):
        for file in files:
            file_path = os.path.join(root, file)
            search_files(code, file_path)

    return matching_files


