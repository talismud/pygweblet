# Copyright (c) 2021, LE GOFF Vincent
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.

# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.

# * Neither the name of ytranslate nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""Pygweblet router."""

from pathlib import Path
from types import ModuleType
from typing import Union, TYPE_CHECKING

from pygweblet.route import PygWebRoute

if TYPE_CHECKING:
    from pygweblet.server import PygWebServer

# Constants
WEB_METHODS = {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}


class PygWebRouter:

    """A Pygweblet router, responsibles for routes.

    An instance of this object is created by the PygWebServer.  Routes
    are handled and automatically created in the router instance.

    The router instance can be iterated over, like a list:

        for route in server.router:
            print(route)

    Each route can then be examined to see if it's linked to a program
    or a template (possibly both).

    """

    def __init__(self, server: "PygWebServer"):
        self.server = server
        self._routes = {}

    def __iter__(self):
        return iter(self._routes.values())

    def load(self, base_dir: Union[str, Path]):
        """Load the routes from the file system.

        Args:
            base_dir (str, Path): the base directory in which routes
                    are stored.

        """
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)

        self._load_programs(base_dir / "programs")
        self._load_templates(base_dir / "pages")

    def _load_programs(self, program_dir: Path):
        """Load the programs, creating routes if needed.

        Args:
            program_dir (Path): the directory containing programs.

        """
        for file_path in program_dir.rglob("*.py"):

            if file_path.name.startswith("_") or any(
                path.name.startswith("_") for path in file_path.parents
            ):
                continue

            # The path may containg characters that disqualify
            # it from being a Python module.  So we oen the file
            # and execute it.
            program_path = file_path.relative_to(program_dir)
            path = self._make_path_from(program_path)
            self._load_program(path, file_path)

    def _load_program(self, path: str, file_path: Path) -> None:
        """Load a program, reading and executing the Python file.

        Args:
            path (str): the URI's path.
            file_path (Path): the path to the Python file.

        """
        with file_path.open("r", encoding="utf-8") as file:
            contents = file.read()

        # Create a module and execute the contents as Python.
        module = ModuleType(f"virtual module at {file_path.as_posix()}")
        exec(contents, module.__dict__)

        # Create corresponding routes.
        for method in WEB_METHODS:
            handler = getattr(module, method.lower(), None)
            if handler is not None:
                self._routes[(method, path)] = PygWebRoute(
                    self, path, method, program=handler
                )

    def _load_templates(self, template_path: Path):
        pass

    @staticmethod
    def _make_path_from(path: Path) -> str:
        """Return an URI path from a file-system path.

        Args:
            path (Path): the path name.

        """
        uri = "/"
        parent = path.parent.as_posix()
        if parent != ".":
            uri += parent

        stem = path.stem
        if stem == "index":
            if uri != "/":
                uri += "/"
        else:
            uri += stem

        return uri
