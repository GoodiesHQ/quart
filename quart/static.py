import mimetypes
import os
import pkgutil
import sys
from pathlib import Path
from typing import AnyStr, Optional
from typing.io import IO

from aiofiles import open as async_open
from jinja2 import FileSystemLoader

from .exceptions import NotFound
from .globals import current_app
from .wrappers import Response

DEFAULT_MIMETYPE = 'application/octet-stream'


class PackageStatic:

    def __init__(
            self,
            import_name: str,
            template_folder: Optional[str]=None,
            root_path: Optional[str]=None,
    ) -> None:
        self.import_name = import_name
        self.template_folder = template_folder

        self.root_path = self._find_root_path(root_path)

        self._static_folder: Optional[str] = None
        self._static_url_path: Optional[str] = None

    @property
    def static_folder(self) -> Optional[str]:
        if self._static_folder is not None:
            return os.path.join(self.root_path, self._static_folder)
        else:
            return None

    @static_folder.setter
    def static_folder(self, static_folder: str) -> None:
        self._static_folder = static_folder

    @property
    def static_url_path(self) -> Optional[str]:
        if self._static_url_path is not None:
            return self._static_url_path
        if self.static_folder is not None:
            return '/' + os.path.basename(self.static_folder)
        else:
            return None

    @static_url_path.setter
    def static_url_path(self, static_url_path: str) -> None:
        self._static_url_path = static_url_path

    @property
    def has_static_folder(self) -> bool:
        return self.static_folder is not None

    @property
    def jinja_loader(self) -> Optional[FileSystemLoader]:
        if self.template_folder is not None:
            return FileSystemLoader(
                os.path.join(self.root_path, self.template_folder),
            )
        else:
            return None

    async def send_static_file(self, filename: str) -> Response:
        if not self.has_static_folder:
            raise RuntimeError('No static folder for this object')
        return await send_from_directory(self.static_folder, filename)

    def open_resource(self, path: str, mode: str='rb') -> IO[AnyStr]:
        """Open a file for reading.

        Use as

        .. code-block:: python

            with app.open_resouce(path) as file_:
                file_.read()
        """
        if mode not in {'r', 'rb'}:
            raise ValueError('Files can only be opened for reading')
        return open(os.path.join(self.root_path, path), mode)

    def _find_root_path(self, root_path: Optional[str]=None) -> str:
        if root_path is not None:
            return root_path
        else:
            module = sys.modules.get(self.import_name)
            if module is not None and hasattr(module, '__file__'):
                file_path = module.__file__
            else:
                loader = pkgutil.get_loader(self.import_name)
                if loader is None or self.import_name == '__main__':
                    return os.getcwd()
                else:
                    file_path = loader.get_filename(self.import_name)  # type: ignore
            return os.path.dirname(os.path.abspath(file_path))


def safe_join(directory: str, *paths: str) -> Path:
    """Safely join the paths to the known directory to return a full path.

    Raises:
        NotFound: if the full path does not share a commonprefix with
        the directory.
    """
    safe_path = Path(directory).resolve()
    full_path = Path(directory, *paths).resolve()
    if not str(full_path).startswith(str(safe_path)):
        raise NotFound()
    return full_path


async def send_from_directory(directory: str, file_name: str) -> Response:
    file_path = safe_join(directory, file_name)
    if not os.path.isfile(file_path):
        raise NotFound()
    return await send_file(file_path)  # type: ignore


async def send_file(filename: str) -> Response:
    mimetype = mimetypes.guess_type(os.path.basename(filename))[0] or DEFAULT_MIMETYPE
    async with async_open(filename, mode='rb') as file_:
        data = await file_.read()
    return current_app.response_class(data, mimetype=mimetype)
