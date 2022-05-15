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

"""Pygweblet WebSocket router."""

from asyncio import iscoroutinefunction
from inspect import isasyncgenfunction
import json
from operator import attrgetter
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Tuple, Union, TYPE_CHECKING

import aiohttp
from aiohttp import web
from pydantic import ValidationError

from pygweblet.packet import PygWebPacket

if TYPE_CHECKING:
    from pygweblet.server import PygWebServer


class PygWebWSRouter:

    """A WebSocket router with packets.

    PygWebLet can offer one or more WebSocket entrypoints.  If a client
    requests for one of them, the messages sent by him will be handled
    by this router.

    """

    def __init__(self, server: "PygWebServer"):
        self.server = server
        self._packets: Dict[str, PygWebPacket] = {}

    def __repr__(self):
        lines = ["<PygWebWSRouter("]
        for packet in self:
            lines.append(" " * 4 + repr(packet))
        lines.append(")>")
        return "\n".join(lines)

    def __str__(self):
        lines = ["PygWebWSRouter("]
        for packet in sorted(self, key=attrgetter("path")):
            lines.append(" " * 4 + str(packet))
        lines.append(")")
        return "\n".join(lines)

    def __iter__(self):
        return iter(self._packets.values())

    def load(self, base_dir: Union[str, Path]):
        """Load the packets from the file system.

        Args:
            base_dir (str, Path): the base directory in which packets
                    are stored.

        """
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)

        packet_dir = base_dir / "packets"
        for file_path in packet_dir.rglob("*.py"):
            if file_path.name.startswith("_") or any(
                path.name.startswith("_") for path in file_path.parents
            ):
                continue

            # The path may contain characters that disqualify
            # it from being a Python module.  So we open the file
            # and execute it.
            packet_path = file_path.relative_to(packet_dir)
            self._load_packet(file_path, packet_path)

    def _load_packet(self, file_path: Path, relative: Path):
        """Load packets, reading and executing the Python file.

        Args:
            file_path (Path): the path to the Python file.

        """
        with file_path.open("r", encoding="utf-8") as file:
            contents = file.read()

        # Create a module and execute the contents as Python.
        module = ModuleType(f"virtual module at {file_path.as_posix()}")
        exec(contents, module.__dict__)

        # Create corresponding packets.
        for name, value in module.__dict__.items():
            if name.startswith("_"):
                continue

            if getattr(value, "__module__", "") != module.__name__:
                # `value` hasn't been defined in this module.
                continue

            if iscoroutinefunction(value) or isasyncgenfunction(value):
                # Add the packet.
                packet_path = self._make_path_for(relative, name)
                packet = PygWebPacket.from_coroutine(self, packet_path, value)
                self._packets[packet_path] = packet

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        """Handle a WebSocket connection.

        Args:
            request (Request): the request to handle.

        Messages are handled as packets (if valid).

        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self.handle_message(ws, msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

        return ws

    async def handle_message(self, ws: web.WebSocketResponse, message: str):
        """Handle the WebSocket message, creating a packet.

        The message should be a JSON-formatted string.  The JSON itself
        should be a collection of two elements: the first one, a string,
        should contain the packet name (a dot separated path), while
        the second one, a dictionary, contains the arguments to send
        to this handler.

        If a packet with the proper path is found, then the handler
        valides the data to make sure it matches what is expected
        by the packet, defined in type hints.  If the JSON is not
        well-formatted or the packet cannot process the sent data,
        this method handles and returns errors.  Otherwise,
        the packet is executed and awaited.

        Args:
            message (str): the message to parse.

        """
        result = self.parse(message)
        if isinstance(result, str):
            # That's an error, send it to the WebSocketClient.
            await ws.send_str(json.dumps({"error": result}))
        else:
            # This is a correct packet, but it might not be valid regardless.
            path, args = result
            packet = self._packets.get(path)
            if packet is None:
                error = f"the packet name {path} is not valid"
                await ws.send_str(json.dumps({"error": error}))
            else:
                # Validate the data for this packet.
                try:
                    arguments = packet.validator(**result[1])
                except ValidationError as err:
                    await ws.send_str(json.dumps({"error": str(err)}))
                else:
                    await packet.handle(ws, arguments.dict())

    def parse(self, message: str) -> Union[str, Tuple[str, Dict[str, Any]]]:
        """Try and parse a JSON packet.

        Args:
            message (str): the JSON packet.

        Returns:
            packet or error: the packet, as a tuple of
                    (packet_path, argments as dict) or an error message
                    (as str).

        """
        try:
            parsed: Tuple[str, Dict[str, Any]] = json.loads(message)
        except json.JSONDecodeError as err:
            return str(err)

        if not isinstance(parsed, list):
            return (
                "the packet should be a list [packet name, "
                "{arg1: whatever, ...}]"
            )

        # This list should contain only two elements.
        if len(parsed) != 2:
            return (
                "two (2) elements should be included in the list: "
                "the packet name (as a string) and the argments "
                "(as a dictionary).  It can be an empty dictionary, "
                "but it has to be present."
            )

        # The first element should be a string.
        if not isinstance(parsed[0], str):
            return (
                "the first element should be a string, but "
                f"{type(parsed[0])} received"
            )

        # The second element should be a dictionary.
        if not isinstance(parsed[1], dict):
            return (
                "the second element should be a dictionary, but "
                f"{type(parsed[1])} received"
            )

        # The second element (a dict) should contain only strings as keys.
        if not all(isinstance(key, str) for key in parsed[1].keys()):
            return (
                "the second element should be a dictionary containing "
                "only strings as keys.  The specified arguments aren't valid."
            )

        return tuple(parsed)

    @staticmethod
    def _make_path_for(path: Path, name: str) -> str:
        """Make a packet path from the file system.

        Args:
            path (Path): the file-system path leading to the Python module.
            name (str): the packet name.

        Returns:
            packet_path (str): the packet path.

        """
        parts = [part for part in path.parent.parts if part != "index"]
        stem = path.stem
        if stem != "index":
            parts.append(stem)

        parts.append(name)
        return ".".join(parts)
