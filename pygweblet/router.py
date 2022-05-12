# Copyright (c) 2022, LE GOFF Vincent
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

from operator import attrgetter
from pathlib import Path
from types import ModuleType
from typing import Union, TYPE_CHECKING

from pygweblet.route import PygWebRoute

if TYPE_CHECKING:
    from pygweblet.server import PygWebServer

# Constants
WEB_METHODS = {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
WEB_METHODS_TO_ADD = {"GET", "POST"}


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

    def __repr__(self):
        lines = ["<PygWebRouter("]
        for route in self:
            lines.append(" " * 4 + repr(route))
        lines.append(")>")
        return "\n".join(lines)

    def __str__(self):
        lines = ["PygWebRouter("]
        for route in sorted(self, key=attrgetter("path", "method")):
            lines.append(" " * 4 + str(route))
        lines.append(")")
        return "\n".join(lines)

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
                    self, path, method, program=handler, program_path=file_path
                )

    def _load_templates(self, template_dir: Path):
        """Load all templates from the custom directory.

        Args:
            template_dir (Path): the directory containing templates.

        """
        for file_path in template_dir.rglob("*.jj2"):
            if file_path.name.startswith("_") or any(
                path.name.startswith("_") for path in file_path.parents
            ):
                continue

            template_path = file_path.relative_to(template_dir)
            file_path = file_path.relative_to(template_dir.parent)
            path = self._make_path_from(template_path)
            self._load_template(path, file_path, template_path)

    def _load_template(
        self, path: str, file_path: Path, relative_path: Path
    ) -> None:
        """Load a template, delegating reading it to the temlate loader.

        Args:
            path (str): the URI's path.
            file_path (Path): the path to the template file.
            relative_path (Path): the path relative to the template directory.

        """
        # If the file's stem is a method name, recalibrate the path.
        stem = file_path.stem
        if stem in WEB_METHODS:
            path = self._make_path_from(relative_path.parent)
            methods = [stem.upper()]
        else:
            methods = tuple(WEB_METHODS_TO_ADD)

        environment = self.server.template_environment
        for method in methods:
            # Add this template to the specific method's route,
            # or create a new route if necessary.
            route = self._routes.get((method, path))
            environment.get_template(file_path.as_posix())
            if route:
                route.template = file_path.as_posix()
            else:
                self._routes[(method, path)] = PygWebRoute(
                    self, path, method, template=file_path.as_posix()
                )

    @staticmethod
    def _make_path_from(path: Path) -> str:
        """Return an URI path from a file-system path.

        Args:
            path (Path): the path name.

        """
        parts = []
        parent = path.parent.as_posix()
        if parent != ".":
            parts += parent.split("/")

        stem = path.stem
        if stem == "index":
            parts.append("")
        else:
            parts.append(stem)

        # Replace dynamic URI parts.
        for i, part in enumerate(parts):
            if part.startswith("(") and part.endswith(")"):
                parts[i] = "{" + part[1:-1] + "}"

        return "/" + "/".join(parts)
