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

"""Pygweblet server."""

import asyncio
from pathlib import Path
from typing import Union

from aiohttp import web
from jinja2 import Environment

from pygweblet.router import PygWebRouter
from pygweblet.template_loader import PygWebTemplateLoader
from pygweblet.websocket import PygWebWSRouter


class PygWebServer:

    """A Pygweblet server, to be started and configured.

    One server will listen to connections on one (or more) port(s).
    and can have different settings from others in the same process.
    See the constructor below for details of the supported options.

    To start a server, in a coroutine, simply await the newly-created
    server insteance's `serve` method:

        import asyncio
        from pygweblet import PygWebServer

        async def main():
            server = PygWebServer()
            await server.serve()

        asyncio.run(main())

    Construction parameters:

        -   `base_dir`: the base directory, as a string or
                a `pathlib.Path` object, representing the directory
                where the routes should be found.
        -   `port`: the port on which to listen for this server.

    """

    def __init__(self, base_dir: Union[str, Path], port: int):
        self.base_dir = base_dir
        self.interface = "127.0.0.1"
        self.port = port
        self.app = web.Application()
        self.runner = web.AppRunner(self.app)
        self.serving_task = None
        self.stop_event = asyncio.Event()
        self.router = PygWebRouter(self)
        self.ws_router = PygWebWSRouter(self)
        self.template_environment = Environment(
            enable_async=True, loader=PygWebTemplateLoader(Path(base_dir))
        )
        self._loaded = False

    async def serve(self):
        """Start the web server, listening to connections."""
        if not self._loaded:
            self.load()

        self.serving_task = asyncio.create_task(self._serve())
        await self.stop_event.wait()

    def cancel(self):
        """If started, cancel the webserver's task, stop lstening."""
        if self.serving_task:
            self.serving_task.cancel()
        self.stop_event.set()

    def load(self):
        """Load the resources from the file system."""
        if self._loaded:
            return

        self.router.load(self.base_dir)
        self.ws_router.load(self.base_dir)
        aio_routes = []
        for route in self.router:
            aio_method = getattr(web, route.method.lower(), None)
            if aio_method is None:
                raise ValueError(
                    f"Method {route.method} for route {route.path} "
                    "cannot be found"
                )

            aio_routes.append(aio_method(route.path, route.handle))

        self.app.add_routes(aio_routes)
        self._loaded = True

    async def _serve(self):
        """Coroutine to start serving."""
        try:
            await self.serve_web()
        except asyncio.CancelledError:
            pass
        except Exception as err:
            raise err

    async def serve_web(self):
        """Asynchronously start the web server."""
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.interface, self.port)
        await site.start()
        self.serving_task = None

    def add_websocket(self, route: str):
        """Add a route for a WebSocket endpoint.

        Args:
            route (str): the route leading to the WebSocket.

        """
        self.app.add_routes([web.get(route, self.ws_router.handle)])
