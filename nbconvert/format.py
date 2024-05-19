import ast
import os
from collections import deque


class StaticAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.class_def = set()
        self.function_def = set()
        self.function_param_def = set()
        self.import_def = set()
        self.alias_def = set()
        self.assign_def = set()
        self.func_call = set()

    def visit_ClassDef(self, node):
        if isinstance(node, ast.ClassDef):
            self.class_def.add(node.name)
            for func in node.body:
                if isinstance(func, ast.FunctionDef) or isinstance(func, ast.AsyncFunctionDef):
                    self.function_def.add(node.name)
                    for arg in node.args.args:
                        self.function_param_def.add(arg.arg)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if isinstance(node, ast.FunctionDef):
            self.function_def.add(node.name)
            for arg in node.args.args:
                self.function_param_def.add(arg.arg)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        if isinstance(node, ast.FunctionDef):
            self.function_def.add(node.name)
            for arg in node.args.args:
                self.function_param_def.add(arg.arg)
        self.generic_visit(node)

    def visit_Assign(self, node):
        if isinstance(node, ast.Assign):
            for i, target in enumerate(node.targets):
                target_dict = target.__dict__
                if "elts" in target_dict:
                    for elt in target_dict.get("elts"):
                        self.assign_def.add(elt.id)
                try:
                    self.assign_def.add(node.value.elt.id)
                except:
                    pass
                self.assign_def.add(target_dict.get("id"))
        self.generic_visit(node)

    def visit_Import(self, node):
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.import_def.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                self.alias_def.add(alias.name)
            module = node.module
            if module:
                self.import_def.add(module)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if isinstance(node, ast.ImportFrom):
            for name in node.names:
                self.import_def.add(node.module)
                self.import_def.add(name.name)
                self.alias_def.add(name.asname)
        self.generic_visit(node)

    def visit_With(self, node):
        if isinstance(node, ast.With):
            for item in node.items:
                try:
                    self.assign_def.add(item.optional_vars.id)
                except:
                    pass
            self.generic_visit(node)

    def visit_For(self, node):
        if isinstance(node, ast.For):
            try:
                if isinstance(node.target, ast.Name):
                    self.assign_def.add(node.target.id)
                elif isinstance(node.target, ast.Tuple):
                    # BFS (Might have Tuple inside tuple)
                    queue = deque()
                    for target in node.target.elts:
                        queue.append(target)
                    while len(queue) > 0:
                        target = queue.popleft()
                        if isinstance(target, ast.Name):
                            self.assign_def.add(target.id)
                        elif isinstance(target, ast.Tuple):
                            for t in target.elts:
                                queue.append(t)
            except:
                pass
        self.generic_visit(node)

    def visit_alias(self, node):
        if isinstance(node, ast.alias):
            self.alias_def.add(node.asname)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node, ast.Call):
            try:
                func_name = node.func.id
                self.func_call.add(func_name)
                for arg in node.args:
                    self.assign_def.add(arg.id)
            except:
                pass
        self.generic_visit(node)


def handle_missing_variables(code_buffer, cell_tag = None):
    undefined_variables = set()
    unimport_function = set()

    def _visit_node_for_undefined_variables(node, analyzer):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            variable_name = node.id

            # Check if the variable is not defined locally and is not a function parameter
            if variable_name not in analyzer.class_def and \
                    variable_name not in analyzer.function_def and \
                    variable_name not in analyzer.function_param_def and \
                    variable_name not in analyzer.import_def and \
                    variable_name not in analyzer.alias_def and \
                    variable_name not in analyzer.assign_def and \
                    variable_name not in __builtins__:
                undefined_variables.add(variable_name)

    try:
        buffer_tree = ast.parse(code_buffer)
        analyzer = StaticAnalyzer()
        analyzer.visit(buffer_tree)

        # Then, visit the tree again to collect undefined variables
        for node in ast.walk(buffer_tree):
            _visit_node_for_undefined_variables(node, analyzer)

        # Visit for unimport function
        for func_call in analyzer.func_call:
            if func_call not in analyzer.function_def and \
                    func_call not in analyzer.import_def and \
                    func_call not in analyzer.alias_def and \
                    func_call not in __builtins__:
                unimport_function.add(func_call)

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
                    import_module = '/'.join(sub_module.split(".")) + '.py'
                    for func in missing_import[sub_module]:
                        if import_module in curr_file and func in file_content:
                            matching_files.add(curr_file)
                            return
                else:
                    if missing_import in curr_file:
                        matching_files.add(curr_file)
                        return

                next_curr_dir = os.path.dirname(curr_file)
                search_files(file_content, next_curr_dir)

    for root, dirs, files in os.walk(project_directory):
        for file in files:
            file_path = os.path.join(root, file)
            search_files(code, file_path)

    return matching_files
