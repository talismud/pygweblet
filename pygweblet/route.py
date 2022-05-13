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

from inspect import signature
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Type, TYPE_CHECKING

from aiohttp import web

from pygweblet.parameter import RouteParameter

if TYPE_CHECKING:
    from pygweblet.router import PygWebRouter

# Constants
ACCEPT_POST_DATA = {"POST", "PUT"}


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
        program: Optional[Callable] = None,
        program_class: Optional[Type[Any]] = None,
        program_path: Optional[Path] = None,
        template: Optional[str] = None,
    ):
        self.router = router
        self.path = path
        self.method = method
        self.program = program
        self.program_class = program_class
        self.program_path = program_path
        self.program_params: Dict[str, RouteParameter] = {}
        self.program_params_kind: Set[RouteParameter] = set()
        self.template = template
        if self.program:
            self._extrapolate_program_params()

    def _extrapolate_program_params(self):
        """Extrapolate program parameters to be sent to the handler."""
        parts = self.path.split("/")
        dynamic_parts = [
            part[1:-1]
            for part in parts
            if part.startswith("{") and part.endswith("}")
        ]
        handler = signature(self.program)
        params = handler.parameters
        for name, parameter in params.items():
            if name == "self":
                if self.program_class is None:
                    raise ValueError(
                        f"the route {self.path} has a program {self.program} "
                        "taking 'self' as argument, but this is not "
                        "a class program"
                    )

                kind = RouteParameter.INSTANCE
            elif name == "request":
                kind = RouteParameter.REQUEST
            elif name in dynamic_parts:
                kind = RouteParameter.DYNAMIC_PART
            else:
                if self.method in ACCEPT_POST_DATA:
                    kind = RouteParameter.QUERY_OR_POST
                else:
                    kind = RouteParameter.QUERY

            self.program_params[parameter.name] = kind
            self.program_params_kind.add(kind)

    @property
    def __repr__(self):
        return f"<Route({self.path!r}, method={self.method})>"

    def __str__(self):
        desc = f"{self.method} {self.path}"
        params = []
        if self.program:
            params.append(f"program={self.program_origin}")
        if self.template:
            params.append(f"template={self.template}")

        return f"{desc} ({', '.join(params)})"

    @property
    def program_origin(self) -> str:
        """Return the address of the program."""
        path = self.program_path and self.program_path.as_posix() or "[...]"
        origin = f"file {path}"
        callback = "function"
        if self.program_class:
            origin += f", class {self.program_class.__name__}"
            callback = "method"

        if self.program:
            origin += f", {callback} {self.program.__name__}"

        return origin

    @property
    def template_environment(self):
        """Return the template environment of the server."""
        return self.router.server.template_environment

    async def handle(self, request):
        """Handle the request, redirecting to program and template.

        Args:
            request (Request): the request to handle.

        """
        if self.program:
            # If needed, create a program class instance.
            instance = None
            kwargs = {}
            if self.program_class:
                instance = self.program_class()
                instance.request = request

            # If necessary, load query parameters.
            info, query, post = {}, {}, {}
            if RouteParameter.DYNAMIC_PART in self.program_params_kind:
                info = request.match_info
            if RouteParameter.QUERY in self.program_params_kind:
                query = request.query
            if RouteParameter.QUERY_OR_POST in self.program_params_kind:
                post = await query.post()

            for name, kind in self.program_params.items():
                if kind is RouteParameter.INSTANCE:
                    kwargs[name] = instance
                elif kind is RouteParameter.DYNAMIC_PART:
                    kwargs[name] = info.get(name)
                elif kind is RouteParameter.REQUEST:
                    kwargs[name] = request
                elif kind is RouteParameter.QUERY:
                    kwargs[name] = query.get(name)
                elif kind is RouteParameter.QUERY_OR_POST:
                    kwargs[name] = query.get(name) or post.get(name)

            # Execute the handler
            result = await self.program(**kwargs)
            if isinstance(result, str):
                return web.Response(text=result, content_type="text/html")

            if self.template:
                template = self.template_environment.get_template(
                    self.template
                )
                text = await template.render_async(**result)
                return web.Response(text=text, content_type="text/html")
