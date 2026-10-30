"""Receive and send Speckle versions through a Speckle server: :func:`receive`, :func:`send`.

A Speckle server publishes a version in one or both of Speckle's data models: as v3 objects
(the JSON object graph the viewer draws) and, since Speckle 4, as a *bundle* (Parquet tables
of properties, scene graph and geometry). A version that exists only as a bundle (its
``referencedObject`` is ``bundle.<project>.<model>.<version>``) has no v3 objects on the
server: :func:`receive` downloads the bundle and projects it to v3 objects with
:func:`bimpolars.bundle.bundle_objects`, so every version comes back as both, ready for
:class:`~specklewidgets.SpeckleViewer` and :func:`bimpolars.read_speckle`.
:func:`send` publishes a BimDataFrame as a new version, as the v3 objects of
:func:`specklewidgets.bim.bim_collection`.

Both use specklepy's v3 pipeline (``ServerTransport``, ``operations.send``,
``version.create``), which specklepy deprecates since 2026.9 in favour of its bundle pipeline;
its DeprecationWarnings are silenced here, by message, as :mod:`specklewidgets.bim` does.

Signing in: :func:`local_client` uses this machine's Speckle account for the server (Speckle
Manager's or a connector's, as specklepy's ``get_local_accounts`` finds them), and
:func:`token_client` a personal access token. The token stays in the client's memory: it is
never written to disk, so a notebook should take it from a password field such as wigglystuff's
``EnvConfig`` (``examples/speckle_receive_send.py``) rather than from its code.

This module needs the ``[server]`` extra (specklepy with its bundle reader) and bimpolars with
its ``[speckle]`` extra; the rest of the package needs neither.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

try:
    from bimpolars.bundle import bundle_objects
    from bimpolars.speckle import SpeckleObject, read_speckle
    from gql.transport.exceptions import TransportServerError
    from specklepy.api import operations
    from specklepy.api.client import SpeckleClient
    from specklepy.api.credentials import get_local_accounts
    from specklepy.api.inputs.version_inputs import CreateVersionInput
    from specklepy.bundle.download import BundleReference, download_bundle
    from specklepy.logging.exceptions import GraphQLException, SpeckleException, SpeckleWarning
    from specklepy.transports.memory import MemoryTransport
    from specklepy.transports.server import ServerTransport
except ImportError as error:
    raise ImportError(
        "specklewidgets.server needs specklepy with its bundle reader and bimpolars with "
        "bimpolars.bundle: install the extra specklewidgets[server] and bimpolars[speckle]"
    ) from error

from specklewidgets.bim import bim_collection

if TYPE_CHECKING:
    import polars as pl
    from bimpolars import BimDataFrame
    from specklepy.api.models import Version

DEFAULT_SERVER = "https://app.speckle.systems"
"""Speckle's own server, where a server argument without one points."""

SOURCE_APPLICATION = "specklewidgets"
"""The ``sourceApplication`` of the versions :func:`send` creates."""

_DEPRECATIONS = (
    r".*JSON based send/receive pipelines are deprecated",
    r".*VersionResource\.Create is deprecated",
)
"""The DeprecationWarnings of specklepy's v3 pipeline and of ``version.create``, which this
module uses on purpose."""

_REFUSED = frozenset({401, 403})
"""The HTTP status codes with which a Speckle server refuses a token."""


@dataclass(frozen=True)
class ReceivedVersion:
    """A Speckle version as :func:`receive` gives it: its v3 objects and its bundle.

    Attributes:
        server: The server's URL, ``https://app.speckle.systems``.
        project_id: The Speckle project id.
        model_id: The Speckle model id.
        version_id: The Speckle version id.
        objects: The version's v3 objects, parsed, the root first and its closure after it:
            a model as :class:`~specklewidgets.SpeckleViewer` and
            :func:`bimpolars.read_speckle` take it.
        bundle: The folder holding the version's bundle, its ``<name>.<table>.parquet``
            files, or None when the server has no bundle for it (a Speckle 2 server, or a
            version older than the server's bundles).
        v3_route: Where the v3 objects come from: ``"server"`` when the server has them,
            ``"projected"`` when the version is bundle-only and they are projected from the
            bundle.
    """

    server: str
    project_id: str
    model_id: str
    version_id: str
    objects: list[SpeckleObject]
    bundle: Path | None
    v3_route: Literal["server", "projected"]

    def bimdataframe(self, *, name: str | None = None) -> BimDataFrame:
        """Reads the version into a BimDataFrame: its objects, with its bundle if it has one.

        The bundle gives the elements their Revit categories, parameters and levels, and the
        elements the objects lack their rows; see :func:`bimpolars.read_speckle`.

        Args:
            name: The CRS's name; the root's or the bundle's model name by default.

        Returns:
            One row per element.
        """
        return read_speckle(self.objects, self.bundle, name=name)


def local_client(server: str = DEFAULT_SERVER) -> SpeckleClient | None:
    """A client signed in with this machine's Speckle account for a server.

    The accounts are those Speckle Manager and the Speckle connectors store, as specklepy's
    ``get_local_accounts`` reads them (``SPECKLE_USERDATA_PATH`` moves their folder), whose
    server URL has the server's host. The default account is tried first, and an account
    whose token the server refuses is passed over, also when another account of the same user
    follows (specklepy's ``get_accounts_for_server`` keeps one account per user, whichever it
    lists first).

    Args:
        server: The server's URL; ``https://`` when it has no scheme.

    Returns:
        The signed-in client, or None when the machine has no account for the server whose
        token works.

    Raises:
        specklepy.logging.exceptions.SpeckleException: If the server cannot be reached.
    """
    url = _server_url(server)
    with warnings.catch_warnings():
        # specklepy reads the accounts through its deprecated SQLiteTransport
        for deprecation in _DEPRECATIONS:
            warnings.filterwarnings("ignore", deprecation, DeprecationWarning)
        accounts = get_local_accounts()
    host = urlsplit(url).netloc
    accounts = [account for account in accounts if _host(account.serverInfo.url) == host]
    for account in sorted(accounts, key=lambda account: not account.isDefault):
        client = _client(url)
        try:
            with warnings.catch_warnings():
                # specklepy warns of a refused token and carries on; it is refused below
                warnings.simplefilter("ignore", SpeckleWarning)
                client.authenticate_with_account(account)
            user = client.active_user.get()
        except SpeckleException as error:
            if _refused(error):
                continue
            raise
        if user is not None:
            return client
    return None


def token_client(token: str, server: str = DEFAULT_SERVER) -> SpeckleClient:
    """A client signed in with a personal access token.

    The token is kept in the client only, never written to disk. Make it on the server
    under *Settings*, *Developer*, *Access tokens*, with the scopes ``profile:read`` and
    ``streams:read`` (and ``streams:write`` to send).

    Args:
        token: The personal access token.
        server: The server's URL; ``https://`` when it has no scheme.

    Returns:
        The signed-in client.

    Raises:
        ValueError: If the server refuses the token, or it lacks the ``profile:read`` scope
            that tells whose it is.
        specklepy.logging.exceptions.SpeckleException: If the server cannot be reached.
    """
    url = _server_url(server)
    client = _client(url)
    try:
        client.authenticate_with_token(token)
    except SpeckleException as error:
        if _refused(error):
            raise ValueError(f"{url} refuses the token") from error
        raise
    if client.account.userInfo.id is None:
        raise ValueError(f"{url} does not say whose token it is: it needs profile:read")
    return client


def receive(
    client: SpeckleClient,
    project_id: str,
    model_id: str,
    version_id: str | None = None,
    *,
    directory: str | os.PathLike[str] | None = None,
) -> ReceivedVersion:
    """Receives a version of a model as its bundle and its v3 objects.

    The bundle's files (geometry shards included) are downloaded into
    ``<directory>/<model id>/<version id>/``, the layout of the bimpolars bucket's
    ``speckle-bundle`` folder. The v3 objects come from the server when it has them, and are
    otherwise projected from the bundle by :func:`bimpolars.bundle.bundle_objects`, which
    keeps the geometry of placed elements and the materials of instance definitions that
    specklepy's own projection loses. The version is not marked as received.

    Args:
        client: A client signed in to the server, from :func:`local_client` or
            :func:`token_client`.
        project_id: The Speckle project id.
        model_id: The Speckle model id.
        version_id: The Speckle version id; the model's latest version by default.
        directory: Where the bundle goes. A new temporary folder by default, which is left
            for the caller (the bundle is read from it), and removed again if the version
            has no bundle.

    Returns:
        The version: ``objects`` and ``bundle`` for :class:`~specklewidgets.SpeckleViewer`
        and :func:`bimpolars.read_speckle`, or :meth:`ReceivedVersion.bimdataframe`.

    Raises:
        ValueError: If the model has no version, the version has no root object (a
            workspace's version history limit hides it), or it is bundle-only and the server
            serves no bundle for it.
        specklepy.logging.exceptions.SpeckleException: If the server refuses or fails a
            request.
    """
    version = _version(client, project_id, model_id, version_id)
    referenced = version.referenced_object
    if not referenced:
        raise ValueError(
            f"version {version.id} has no root object: the workspace's version history "
            "limit may hide it"
        )
    bundle_only = BundleReference.is_reference(referenced)
    if bundle_only:
        # the reference names the bundle's version, which is this version
        reference = BundleReference.parse(referenced)
        model_id, version_id = reference.model_id, reference.version_id
    else:
        version_id = version.id
    temporary = directory is None
    parent = Path(tempfile.mkdtemp(prefix="speckle-bundle-") if directory is None else directory)
    folder = parent / model_id / version_id
    files = download_bundle(client.account, project_id, model_id, version_id, str(folder))
    if not files:
        if temporary:
            shutil.rmtree(parent, ignore_errors=True)
        if bundle_only:
            raise ValueError(
                f"version {version_id} exists only as a bundle, which {client.url} does not serve"
            )
    if bundle_only:
        objects = bundle_objects(folder)
    else:
        objects = _server_objects(client, project_id, referenced)
    return ReceivedVersion(
        server=client.url,
        project_id=project_id,
        model_id=model_id,
        version_id=version_id,
        objects=objects,
        bundle=folder if files else None,
        v3_route="projected" if bundle_only else "server",
    )


def send(
    client: SpeckleClient,
    bdf: BimDataFrame,
    project_id: str,
    model_id: str,
    *,
    message: str | None = None,
    color: str | pl.Expr | None = None,
    name: str | None = None,
) -> str:
    """Sends a BimDataFrame as a new version of a model.

    The objects are those of :func:`specklewidgets.bim.bim_collection`: one DataObject per
    row with a mesh (openings left out), its ``id`` as ``applicationId`` and its ``class`` as
    ``category``, its mesh as one Mesh per style, a RenderMaterial per style, grouped into a
    Collection per class. :func:`receive` and :func:`bimpolars.read_speckle` read them back
    into those rows. The version is a v3 version, without a bundle; its
    ``sourceApplication`` is :data:`SOURCE_APPLICATION`.

    Args:
        client: A client signed in to the server with the right to write to the project.
        bdf: The model.
        project_id: The Speckle project id.
        model_id: The id of the project's model the version goes to.
        message: The version's message.
        color: Colours the elements by a column or an expression instead of by their styles,
            as :func:`specklewidgets.bim.bim_collection` does.
        name: The root collection's name; the CRS's name by default.

    Returns:
        The new version's id.

    Raises:
        ValueError: If a drawn row has no ``id`` or shares it with another, or ``color``
            does not give one value per row.
        TypeError: If ``color`` gives a nested or binary column.
        specklepy.logging.exceptions.SpeckleException: If the server refuses or fails a
            request.
    """
    root = bim_collection(bdf, color=color, name=name)
    with warnings.catch_warnings():
        for deprecation in _DEPRECATIONS:
            warnings.filterwarnings("ignore", deprecation, DeprecationWarning)
        transport = ServerTransport(stream_id=project_id, client=client)
        root_id = operations.send(root, transports=[transport], use_default_cache=False)
        version = client.version.create(
            CreateVersionInput(
                object_id=root_id,
                model_id=model_id,
                project_id=project_id,
                message=message,
                source_application=SOURCE_APPLICATION,
            )
        )
    return str(version.id)


def _server_url(server: str) -> str:
    """A server's URL as ``scheme://host[:port]``, ``https`` when it names no scheme."""
    parts = urlsplit(server if "://" in server else f"https://{server}")
    if not parts.netloc:
        raise ValueError(f"{server!r} names no server")
    return f"{parts.scheme}://{parts.netloc}"


def _host(url: str | None) -> str:
    """The host (and port) of a URL, ``https`` assumed when it names no scheme."""
    if not url:
        return ""
    return urlsplit(url if "://" in url else f"https://{url}").netloc


def _client(url: str) -> SpeckleClient:
    """A client for a server's URL, not signed in yet."""
    parts = urlsplit(url)
    return SpeckleClient(host=parts.netloc, use_ssl=parts.scheme == "https")


def _refused(error: SpeckleException) -> bool:
    """Whether a failed request failed because the server refuses the token."""
    if isinstance(error, GraphQLException):
        return True
    cause = getattr(error, "exception", None)
    return isinstance(cause, TransportServerError) and cause.code in _REFUSED


def _version(
    client: SpeckleClient, project_id: str, model_id: str, version_id: str | None
) -> Version:
    """A version by its id, or the model's latest."""
    if version_id is not None:
        return client.version.get(version_id, project_id)
    versions = client.version.get_versions(model_id, project_id, limit=1).items
    if not versions:
        raise ValueError(f"model {model_id} of project {project_id} has no version")
    return versions[0]


def _server_objects(client: SpeckleClient, project_id: str, root_id: str) -> list[SpeckleObject]:
    """A root object and its closure, from the server, the root first."""
    with warnings.catch_warnings():
        for deprecation in _DEPRECATIONS:
            warnings.filterwarnings("ignore", deprecation, DeprecationWarning)
        memory = MemoryTransport()
        ServerTransport(stream_id=project_id, client=client).copy_object_and_children(
            root_id, memory
        )
    objects: dict[str, str] = memory.objects
    return [
        json.loads(objects[root_id]),
        *(json.loads(text) for object_id, text in objects.items() if object_id != root_id),
    ]


__all__ = [
    "DEFAULT_SERVER",
    "SOURCE_APPLICATION",
    "ReceivedVersion",
    "local_client",
    "receive",
    "send",
    "token_client",
]
