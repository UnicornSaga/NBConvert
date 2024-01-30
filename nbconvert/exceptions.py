class AwsError(Exception):
    """Raised when an AWS Exception is encountered."""


class FileExistsError(AwsError):
    """Raised when a File already exists on S3."""


class NBConvertlException(Exception):
    """Raised when an exception is encountered when operating on a notebook."""


class NBConvertMissingParameterException(NBConvertlException):
    """Raised when a parameter without a value is required to operate on a notebook."""


class NBConvertExecutionError(NBConvertlException):
    """Raised when an exception is encountered in a notebook."""

    def __init__(self, cell_index, exec_count, source, ename, evalue, traceback):
        args = cell_index, exec_count, source, ename, evalue, traceback
        self.cell_index = cell_index
        self.exec_count = exec_count
        self.source = source
        self.ename = ename
        self.evalue = evalue
        self.traceback = traceback

        super().__init__(*args)

    def __str__(self):
        # Standard Behavior of an exception is to produce a string representation of its arguments
        # when called with str(). In order to maintain compatibility with previous versions which
        # passed only the message to the superclass constructor, __str__ method is implemented to
        # provide the same result as was produced in the past.
        message = f"\n{75 * '-'}\n"
        message += f'Exception encountered at "In [{self.exec_count}]":\n'
        message += "\n".join(self.traceback)
        message += "\n"
        return message


class NBConvertRateLimitException(NBConvertlException):
    """Raised when an io request has been rate limited"""


class NBConvertOptionalDependencyException(NBConvertlException):
    """Raised when an exception is encountered when an optional plugin is missing."""


class NBConvertWarning(Warning):
    """Base warning for nbconvert."""


class NBConvertParameterOverwriteWarning(NBConvertWarning):
    """Callee overwrites caller argument to pass down the stream."""


def missing_dependency_generator(package):
    def missing_dep():
        raise NBConvertOptionalDependencyException(
            f"The {package} optional dependency is missing. "
        )

    return missing_dep


def missing_environment_variable_generator(package, env_key):
    def missing_dep():
        raise NBConvertOptionalDependencyException(
            f"The {package} optional dependency is present, but the environment "
            f"variable {env_key} is not set. Please set this variable as "
            f"required by {package} on your platform."
        )

    return missing_dep
