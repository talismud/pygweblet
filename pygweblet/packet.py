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

"""Pygweblet websocket packet."""

from asyncio import iscoroutinefunction
from inspect import isasyncgenfunction, signature
import json
from typing import Any, Callable, Dict, Type, TYPE_CHECKING, get_type_hints

from aiohttp import web
from pydantic import BaseModel

if TYPE_CHECKING:
    from pygweblet.websocket import PygWebWSRouter


class PygWebPacket:

    """A Pygweblet packet for a websocket entrypoint."""

    def __init__(
        self,
        router: "PygWebWSRouter",
        path: str,
        handler: Callable[[], Any],
        validator: Type[BaseModel],
    ):
        self.router = router
        self.path = path
        self.handler = handler
        self.validator = validator

    def __repr__(self) -> str:
        params = [
            f"path={self.path}",
            f"handler={self.handler}",
            f"signature={self.validator.__signature__})",
        ]
        return f"<PygWebPacket({', '.join(params)})>"

    async def handle(
        self, ws: web.WebSocketResponse, arguments: Dict[str, Any]
    ):
        """Handle this packet with the specified arguments.

        Args:
            ws (WebSocketResponse): the websocket response.
            arguments (dict): the packet arguments, already validated.

        """
        handler = self.handler
        if iscoroutinefunction(handler):
            # Executes the coroutine and forwards the result.
            result = await handler(**arguments)
            if isinstance(result, dict):
                await ws.send_str(json.dumps(result))
        elif isasyncgenfunction(handler):
            # `handler` is an async generator, execute it and awaits
            # its termination.
            async for result in handler(**arguments):
                if isinstance(result, dict):
                    await ws.send_str(json.dumps(result))

    @classmethod
    def from_coroutine(
        cls, router: "PygWebWSRouter", path: str, handler: Callable
    ):
        """Generate a packet from a coroutine handler.

        Args:
            router (PygWebWSRouter): the WebSocket router.
            path (str): the packet path.
            handler (Coroutine): the handler itself.

        Returns:
            packet (PygWebPacket): if successful, create a new packet.

        """
        defaults = {
            parameter.name: parameter.default
            for parameter in signature(handler).parameters.values()
            if parameter.default is not parameter.empty
        }
        hints = get_type_hints(handler)
        hints.pop("return", None)
        attributes = defaults
        config = type("Config", (), {"arbitrary_types_allowed": True})
        attributes["__annotations__"] = hints
        attributes["Config"] = config
        validator = type("Validator", (BaseModel,), attributes)
        return PygWebPacket(router, path, handler, validator)
