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

from types import ModuleType
from typing import Optional, TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from pygweblet.router import PygWebRouter


class PygWebRoute:

    """A Pygweblet route, serving a page.

    In PygWebLet, a route is a link between a Uniform Resource Identifier
    (URI), a method, program and template.  In other words, a route tells
    the web server what to do when the client asks for a specific URL.

    PygWebLet offers programs and templates: a program is a Python
    function (or class method) that can add behavior when this URL
    is reached.  The template, on the other hand, tells the web server
    what to return to the client for the page's content.  A page
    can have either a program, a template, or both at once.
    It cannot exist if it has neither program nor template.

    A set of rules is applied to determine the route's method.
    This is the router's responsibility, the route itself is only called
    when the router identifies that the Web client requires it.

    """

    def __init__(
        self,
        router: "PygWebRouter",
        path: str,
        method: str,
        program: Optional[ModuleType] = None,
        template: Optional[str] = None,
    ):
        self.router = router
        self.path = path
        self.method = method
        self.program = program
        self.template = template

    async def handle(self, request):
        """Handle the request, redirecting to program and template.

        Args:
            request (Request): the request to handle.

        """
        if self.program:
            result = await self.program(request)
            if isinstance(result, str):
                return web.Response(text=result, content_type="text/html")
