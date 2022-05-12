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

"""Loader for Jinj12 templates."""

from pathlib import Path
from typing import Callable, Tuple

from jinja2 import BaseLoader, Environment, TemplateNotFound


class PygWebTemplateLoader(BaseLoader):

    """Loader specific to PygWebLet, based on a file-system loader."""

    def __init__(self, path: Path):
        self.path = path

    def get_source(
        self, environment: Environment, template: str
    ) -> Tuple[str, str, Callable[[str], bool]]:
        """Get the compiled template, if found.

        If not found, raise TemplateNotFound exception.

        Args:
            environment (Environment): the Jinja2 environment.
            template (str): the template name (or path).

        Returns:
            content, path, callable (tuple): the content's template as
                    a string, the path as a string and a callable to check
                    that the template hasn't been modified.

        Raises:
            TemplateNotFound if the template isn't found.

        """
        path = self.path / template
        if not path.exists():
            raise TemplateNotFound(template)

        mtime = path.stat().st_mtime
        with path.open("r", encoding="utf-8") as file:
            source = file.read()

        def is_modified() -> bool:
            return mtime == path.stat().st_mtime

        return source, path.as_posix(), is_modified
