import fnmatch
import json
import os
import sys
import warnings
from contextlib import contextmanager

import entrypoints
import nbformat
import requests
import yaml
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from nbconvert.exceptions import (
    NBConvertlException,
    NBConvertRateLimitException,
    missing_dependency_generator,
)
from nbconvert.log import logger
from nbconvert.utils import chdir
from nbconvert.version import version as __version__


try:
    from nbconvert.s3 import S3
except ImportError:
    S3 = missing_dependency_generator("boto3")

try:
    from nbconvert.abs import AzureBlobStore
except ImportError:
    AzureBlobStore = missing_dependency_generator("azure.storage.blob")

try:
    from gcsfs import GCSFileSystem
except ImportError:
    GCSFileSystem = missing_dependency_generator("gcsfs")


def fallback_gs_is_retriable(e):
    try:
        print(e.code)
        return e.code is None or e.code == 429
    except AttributeError:
        print(e)
        return False


try:
    try:
        # Default to gcsfs library's retry logic
        from gcsfs.retry import is_retriable as gs_is_retriable
    except ImportError:
        from gcsfs.utils import is_retriable as gs_is_retriable
except ImportError:
    gs_is_retriable = fallback_gs_is_retriable

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError


class NBConvertIO:
    '''
    The holder which houses any io system registered with the system.
    This object is used in a singleton manner to save and load particular
    named Handler objects for reference externally.
    '''

    def __init__(self):
        self.reset()

    def read(self, path, extensions=['.ipynb', '.json', 'py']):
        notebook_metadata = self.get_handler(path, extensions).read(path)
        if isinstance(notebook_metadata, (bytes, bytearray)):
            return notebook_metadata.decode('utf-8')
        return notebook_metadata

    def write(self, buf, path, extensions=['.ipynb', '.json', 'py']):
        return self.get_handler(path, extensions).write(buf, path)

    def listdir(self, path):
        return self.get_handler(path).listdir(path)

    def pretty_path(self, path):
        return self.get_handler(path).pretty_path(path)

    def reset(self):
        self._handlers = []

    def register(self, scheme, handler):
        # Keep these ordered as LIFO
        self._handlers.insert(0, (scheme, handler))

    def register_entry_points(self):
        # Load handlers provided by other packages
        for entrypoint in entrypoints.get_group_all("nbconvert.io"):
            self.register(entrypoint.name, entrypoint.load())

    def get_handler(self, path, extensions=None):
        '''Get I/O Handler based on a notebook path

        Parameters
        ----------
        path : str or nbformat.NotebookNode or None
        extensions : list of str, optional
            Required file extension options for the path (if path is a string), which
            will log a warning if there is no match. Defaults to None, which does not
            check for any extensions

        Raises
        ------
        NBConvertException: If a valid I/O handler could not be found for the input path

        Returns
        -------
        I/O Handler
        '''
        if path is None:
            return NoIOHandler()

        if isinstance(path, nbformat.NotebookNode):
            return NotebookNodeHandler()

        if extensions:
            if not fnmatch.fnmatch(os.path.basename(path).split('?')[0], '*.*'):
                warnings.warn(f"the file is not specified with any extension : {os.path.basename(path)}")
            elif not any(fnmatch.fnmatch(os.path.basename(path).split('?')[0], f"*{ext}") for ext in extensions):
                warnings.warn(f"The specified file ({path}) does not end in one of {extensions}")

        local_handler = None
        for scheme, handler in self._handlers:
            if scheme == 'local':
                local_handler = handler

            if path.startswith(scheme):
                return handler

        if local_handler is None:
            raise NBConvertlException(f"Could not find a registered schema handler for: {path}")

        return local_handler


class HttpHandler:
    @classmethod
    def read(cls, path):
        return requests.get(path, headers={'Accept': 'application/json'}).text

    @classmethod
    def listdir(cls, path):
        raise NBConvertlException('listdir is not supported by HttpHandler')

    @classmethod
    def write(cls, buf, path):
        result = requests.put(path, json=json.loads(buf))
        result.raise_for_status()

    @classmethod
    def pretty_path(cls, path):
        return path


class LocalHandler:
    def __init__(self):
        self._cwd = None

    def read(self, path):
        try:
            with chdir(self._cwd):
                with open(path, encoding="utf-8") as f:
                    return f.read()
        except OSError as e:
            try:
                # Check if path could be a notebook passed in as a
                # string
                json.loads(path)
                return path
            except ValueError:
                # Propagate the IOError
                raise e

    def listdir(self, path):
        with chdir(self._cwd):
            return [os.path.join(path, fn) for fn in os.listdir(path)]

    def write(self, buf, path):
        with chdir(self._cwd):
            dirname = os.path.dirname(path)
            if dirname and not os.path.exists(dirname):
                os.mkdir(dirname)
            with open(path, 'w', encoding="utf-8") as f:
                f.write(buf)

    def pretty_path(self, path):
        return path

    def cwd(self, new_path):
        '''Sets the cwd during reads and writes'''
        old_cwd = self._cwd
        self._cwd = new_path
        return old_cwd


class S3Handler:
    @classmethod
    def read(cls, path):
        return "\n".join(S3().read(path))

    @classmethod
    def listdir(cls, path):
        return S3().listdir(path)

    @classmethod
    def write(cls, buf, path):
        return S3().cp_string(buf, path)

    @classmethod
    def pretty_path(cls, path):
        return path


class ABSHandler:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = AzureBlobStore()
        return self._client

    def read(self, path):
        lines = self._get_client().read(path)
        return "\n".join(lines)

    def listdir(self, path):
        return self._get_client().listdir(path)

    def write(self, buf, path):
        return self._get_client().write(buf, path)

    def pretty_path(self, path):
        return path


class GCSHandler:
    RATE_LIMIT_RETRIES = 3
    RETRY_DELAY = 1
    RETRY_MULTIPLIER = 1
    RETRY_MAX_DELAY = 4

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = GCSFileSystem()
        return self._client

    def read(self, path):
        with self._get_client().open(path) as f:
            return f.read()

    def listdir(self, path):
        return self._get_client().ls(path)

    def write(self, buf, path):
        # Wrapped so we can mock retry options during testing
        @retry(
            retry=retry_if_exception_type(NBConvertRateLimitException),
            stop=stop_after_attempt(self.RATE_LIMIT_RETRIES),
            wait=wait_exponential(multiplier=self.RETRY_MULTIPLIER, min=self.RETRY_DELAY, max=self.RETRY_MAX_DELAY),
            reraise=True,
        )
        def retry_write():
            try:
                with self._get_client().open(path, 'w') as f:
                    return f.write(buf)
            except Exception as e:
                try:
                    message = e.message
                except AttributeError:
                    message = f"Generic exception {type(e)} raised"
                if gs_is_retriable(e):
                    raise NBConvertRateLimitException(message)
                # Reraise the original exception without retries
                raise

        return retry_write()

    def pretty_path(self, path):
        return path


class StreamHandler:
    '''Handler for Stdin/Stdout streams'''

    def read(self, path):
        return sys.stdin.read()

    def listdir(self, path):
        raise NBConvertlException('listdir is not supported by Stream Handler')

    def write(self, buf, path):
        try:
            return sys.stdout.buffer.write(buf.encode('utf-8'))
        except AttributeError:
            return sys.stdout.write(buf.encode('utf-8'))

    def pretty_path(self, path):
        return path


class NotebookNodeHandler:
    '''Handler for input_path of nbformat.NotebookNode object'''

    def read(self, path):
        return nbformat.writes(path)

    def listdir(self, path):
        raise NBConvertlException('listdir is not supported by NotebookNode Handler')

    def write(self, buf, path):
        raise NBConvertlException('write is not supported by NotebookNode Handler')

    def pretty_path(self, path):
        return 'NotebookNode object'


class NoIOHandler:
    '''Handler for output_path of None - intended to not write anything'''

    def read(self, path):
        raise NBConvertlException('read is not supported by NoIOHandler')

    def listdir(self, path):
        raise NBConvertlException('listdir is not supported by NoIOHandler')

    def write(self, buf, path):
        return

    def pretty_path(self, path):
        return 'Notebook will not be saved'


class NoDatesSafeLoader(yaml.SafeLoader):
    yaml_implicit_resolvers = {
        k: [r for r in v if r[0] != 'tag:yaml.org,2002:timestamp']
        for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }


# Instantiate a NBConvertIO instance and register Handlers.
nbconvert_io = NBConvertIO()
nbconvert_io.register("local", LocalHandler())
nbconvert_io.register("s3://", S3Handler)
nbconvert_io.register("minio://", S3Handler)
nbconvert_io.register("gs://", GCSHandler())
nbconvert_io.register("abs://", ABSHandler())
nbconvert_io.register("http://", HttpHandler)
nbconvert_io.register("https://", HttpHandler)
nbconvert_io.register("-", StreamHandler())
nbconvert_io.register_entry_points()


def read_yaml_file(path):
    """Reads a YAML file from the location specified at 'path'."""
    return yaml.load(nbconvert_io.read(path, ['.json', '.yaml', '.yml']), Loader=NoDatesSafeLoader)


def write_ipynb(nb, path):
    """Saves a notebook object to the specified path.
    Args:
        nb_node (nbformat.NotebookNode): Notebook object to save.
        notebook_path (str): Path to save the notebook object to.
    """
    nbconvert_io.write(nbformat.writes(nb), path)

def write_py(nb_buffer, path):
    nbconvert_io.write(nb_buffer, path)


def load_notebook_node(notebook_path):
    """Returns a notebook object with nbconvert metadata loaded from the specified path.

    Args:
        notebook_path (str): Path to the notebook file.

    Returns:
        nbformat.NotebookNode

    """
    nb = nbformat.reads(nbconvert_io.read(notebook_path), as_version=4)
    nb_upgraded = nbformat.v4.upgrade(nb)
    if nb_upgraded is not None:
        nb = nb_upgraded

    if not hasattr(nb.metadata, 'nbconvert'):
        nb.metadata['nbconvert'] = {
            'default_parameters': dict(),
            'parameters': dict(),
            'environment_variables': dict(),
            'version': __version__,
        }

    for cell in nb.cells:
        if not hasattr(cell.metadata, 'tags'):
            cell.metadata['tags'] = []  # Create tags attr if one doesn't exist.

        if not hasattr(cell.metadata, 'nbconvert'):
            cell.metadata['nbconvert'] = dict()

    return nb


def list_notebook_files(path):
    """Returns a list of all the notebook files in a directory."""
    return [p for p in nbconvert_io.listdir(path) if p.endswith('.ipynb')]


def get_pretty_path(path):
    return nbconvert_io.pretty_path(path)


@contextmanager
def local_file_io_cwd(path=None):
    try:
        local_handler = nbconvert_io.get_handler("local")
    except NBConvertlException:
        logger.warning("No local file handler detected")
    else:
        try:
            old_cwd = local_handler.cwd(path or os.getcwd())
        except AttributeError:
            logger.warning("Local file handler does not support cwd assignment")
        else:
            try:
                yield
            finally:
                local_handler.cwd(old_cwd)
