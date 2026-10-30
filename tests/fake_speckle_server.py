"""A Speckle server on localhost that answers what specklewidgets.server asks of one.

It speaks the parts of Speckle's API specklepy uses to sign in, receive and send: the GraphQL
queries of the server info, the active user and versions and the version mutation, the REST
routes of ServerTransport (``/objects/<project>/<id>/single``, ``/api/getobjects``,
``/api/diff``, ``/objects/<project>`` uploads) and the ``/api/v2`` artifact listing of a
version's bundle with its files behind "presigned" URLs. Every route but the server info and
the files wants ``Authorization: Bearer <token>`` and answers 403 without it, as a server
refusing a token does; a token in ``graphql_errors`` gets a GraphQL error with that code
instead. The state is plain dicts, for the tests to fill and read, and ``requests`` lists
each request with whether it carried an ``Authorization`` header.
"""

from __future__ import annotations

import gzip
import json
import secrets
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from email.parser import BytesParser
from email.policy import HTTP
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs


class FakeSpeckleServer:
    """The state of the fake server and the URL it listens on.

    Attributes:
        token: The one token the server takes.
        objects: Per project, the JSON text of each object by id.
        versions: Per (project, model), the versions as the GraphQL API gives them, the
            latest first.
        bundles: Per (project, model, version), the files of the version's bundle by name.
        graphql_errors: Tokens the GraphQL API answers with an error of this code
            (``extensions.code``), such as ``FORBIDDEN``, instead of a 403.
        requests: Each request's method, path and whether it carried ``Authorization``.
    """

    def __init__(self, token: str = "fake-token") -> None:
        self.token = token
        self.objects: dict[str, dict[str, str]] = {}
        self.versions: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.bundles: dict[tuple[str, str, str], dict[str, Path]] = {}
        self.graphql_errors: dict[str, str] = {}
        self.requests: list[tuple[str, str, bool]] = []
        self.url = ""

    def add_objects(self, project_id: str, objects: list[Mapping[str, Any]]) -> None:
        """Stores v3 objects in a project, by their ids."""
        stored = self.objects.setdefault(project_id, {})
        for obj in objects:
            stored[obj["id"]] = json.dumps(obj)

    def add_version(
        self,
        project_id: str,
        model_id: str,
        referenced_object: str,
        *,
        version_id: str | None = None,
        message: str | None = None,
        source_application: str | None = None,
    ) -> dict[str, Any]:
        """Adds a version to a model, as its latest, and gives it."""
        version = {
            "id": version_id or secrets.token_hex(5),
            "referencedObject": referenced_object,
            "message": message,
            "sourceApplication": source_application,
            "createdAt": "2026-10-30T12:00:00Z",
            "previewUrl": "",
            "authorUser": None,
        }
        self.versions.setdefault((project_id, model_id), []).insert(0, version)
        return version

    def add_bundle(self, project_id: str, model_id: str, version_id: str, folder: Path) -> None:
        """Serves the Parquet files of a folder as a version's bundle."""
        self.bundles[(project_id, model_id, version_id)] = {
            path.name: path for path in sorted(folder.iterdir()) if path.suffix == ".parquet"
        }

    @contextmanager
    def running(self) -> Iterator[FakeSpeckleServer]:
        """Listens on a free port of 127.0.0.1 while the block runs."""
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        httpd.fake = self  # type: ignore[attr-defined]
        self.url = f"http://127.0.0.1:{httpd.server_address[1]}"
        thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
        thread.start()
        try:
            yield self
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()

    def graphql(self, query: str, variables: Mapping[str, Any], authorized: bool) -> Any:
        """The ``data`` of a GraphQL answer, or None for a refused request."""
        if "serverInfo" in query:
            if "data:version" in query:
                return {"data": {"data": "2026.9.0"}}
            return {
                "data": {
                    "name": "Fake Speckle",
                    "company": None,
                    "description": None,
                    "adminContact": None,
                    "canonicalUrl": self.url,
                    "version": "2026.9.0",
                    "scopes": [],
                    "authStrategies": [],
                    "workspaces": {"workspacesEnabled": False},
                }
            }
        if not authorized:
            return None
        if "activeUser" in query:
            return {
                "data": {
                    "id": "fake-user",
                    "email": "user@example.com",
                    "name": "Fake User",
                    "bio": None,
                    "company": None,
                    "avatar": None,
                    "verified": True,
                    "role": "server:user",
                }
            }
        if "query VersionGetVersions" in query:
            versions = self.versions.get((variables["projectId"], variables["modelId"]), [])
            items = versions[: variables["limit"]]
            page = {"items": items, "cursor": None, "totalCount": len(versions)}
            return {"data": {"data": {"data": page}}}
        if "query VersionGet" in query:
            version = next(
                version
                for (project_id, _), versions in self.versions.items()
                if project_id == variables["projectId"]
                for version in versions
                if version["id"] == variables["versionId"]
            )
            return {"data": {"data": version}}
        if "mutation Create(" in query:
            fields = variables["input"]
            version = self.add_version(
                fields["projectId"],
                fields["modelId"],
                fields["objectId"],
                message=fields["message"],
                source_application=fields["sourceApplication"],
            )
            return {"data": {"data": version}}
        raise NotImplementedError(query)


class _Handler(BaseHTTPRequestHandler):
    """One request to the fake server."""

    server: Any

    def log_message(self, format: str, *args: Any) -> None:
        """Keeps the test output quiet."""

    @property
    def fake(self) -> FakeSpeckleServer:
        fake: FakeSpeckleServer = self.server.fake
        return fake

    @property
    def authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {self.fake.token}"

    def _record(self) -> None:
        self.fake.requests.append((self.command, self.path, "Authorization" in self.headers))

    def do_GET(self) -> None:
        self._record()
        parts = self.path.strip("/").split("/")
        if parts[0] == "files":
            _, project_id, model_id, version_id, name = parts
            path = self.fake.bundles[(project_id, model_id, version_id)][name]
            return self._answer(HTTPStatus.OK, path.read_bytes(), "application/octet-stream")
        if not self.authorized:
            return self._answer(HTTPStatus.FORBIDDEN, b"forbidden")
        if parts[0] == "objects" and parts[-1] == "single":
            _, project_id, object_id, _ = parts
            text = self.fake.objects.get(project_id, {}).get(object_id)
            if text is None:
                return self._answer(HTTPStatus.NOT_FOUND, b"no such object")
            return self._answer(HTTPStatus.OK, text.encode())
        if parts[:3] == ["api", "v2", "projects"] and parts[-1] == "artifacts":
            project_id, model_id, version_id = parts[3], parts[5], parts[7]
            files = self.fake.bundles.get((project_id, model_id, version_id))
            if files is None:
                return self._answer(HTTPStatus.NOT_FOUND, b"no bundle")
            listing = {
                "files": [
                    {
                        "name": name,
                        "url": f"{self.fake.url}/files/{project_id}/{model_id}/{version_id}/{name}",
                    }
                    for name in files
                ]
            }
            return self._json(listing)
        self._answer(HTTPStatus.NOT_FOUND, b"no such route")

    def do_POST(self) -> None:
        self._record()
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        parts = self.path.strip("/").split("/")
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if parts == ["graphql"] and token in self.fake.graphql_errors:
            code = self.fake.graphql_errors[token]
            error = {"message": f"fake {code}", "extensions": {"code": code}}
            return self._json({"errors": [error], "data": None})
        if parts == ["graphql"]:
            request = json.loads(body)
            data = self.fake.graphql(
                request["query"], request.get("variables") or {}, self.authorized
            )
            if data is None:
                return self._answer(HTTPStatus.FORBIDDEN, b"forbidden")
            return self._json({"data": data})
        if not self.authorized:
            return self._answer(HTTPStatus.FORBIDDEN, b"forbidden")
        stored = self.fake.objects.setdefault(parts[-1], {})
        if parts[:2] == ["api", "diff"]:
            ids = json.loads(parse_qs(body.decode())["objects"][0])
            return self._json({object_id: object_id in stored for object_id in ids})
        if parts[:2] == ["api", "getobjects"]:
            ids = json.loads(parse_qs(body.decode())["objects"][0])
            lines = "".join(f"{object_id}\t{stored[object_id]}\n" for object_id in ids)
            return self._answer(HTTPStatus.OK, lines.encode())
        if parts[0] == "objects":
            head = f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode()
            form = BytesParser(policy=HTTP).parsebytes(head + body)
            for part in form.iter_parts():
                batch = gzip.decompress(part.get_payload(decode=True))
                for obj in json.loads(batch):
                    stored[obj["id"]] = json.dumps(obj)
            return self._answer(HTTPStatus.CREATED, b"")
        self._answer(HTTPStatus.NOT_FOUND, b"no such route")

    def _json(self, value: Any) -> None:
        self._answer(HTTPStatus.OK, json.dumps(value).encode(), "application/json")

    def _answer(self, status: HTTPStatus, body: bytes, content_type: str = "text/plain") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
