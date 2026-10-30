"""Receive and send against a fake Speckle server on localhost (fake_speckle_server.py).

The server serves the Revit Advanced Sample's architectural version from the bimpolars bucket,
as a bundle and as v3 objects, so that receiving it can be compared with the bucket's frame,
and stores what a send uploads, so that a round trip runs through specklepy's HTTP requests.
The same checks against a real server are in test_server_live.py.
"""

import json
import os
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pytest

from fake_speckle_server import FakeSpeckleServer
from speckle_objects import revit_like

# bimpolars[speckle], with specklepy's bundle reader, is a dev dependency
data = pytest.importorskip("bimpolars.data")
server = pytest.importorskip("specklewidgets.server")
pl = pytest.importorskip("polars")
from specklepy.logging.exceptions import SpeckleException  # noqa: E402

from round_trip import assert_kept, bucket_version  # noqa: E402

ARCH = data.RVT_SPECKLE_ARCH


@pytest.fixture(scope="module")
def arch() -> Any:
    return bucket_version(ARCH)


@pytest.fixture
def fake() -> Any:
    with FakeSpeckleServer().running() as fake:
        yield fake


@pytest.fixture
def client(fake) -> Any:
    return server.token_client(fake.token, fake.url)


@pytest.fixture
def accounts(monkeypatch, tmp_path) -> Path:
    """An empty folder of local Speckle accounts, where specklepy looks for them."""
    monkeypatch.setenv("SPECKLE_USERDATA_PATH", str(tmp_path))
    folder = tmp_path / "Speckle" / "Accounts"
    folder.mkdir(parents=True)
    return folder


def add_account(folder: Path, url: str, token: str, *, default: bool = False) -> None:
    """A local account as Speckle Manager stores it."""
    account = {
        "id": token,
        "token": token,
        "isDefault": default,
        "serverInfo": {"url": url, "name": "Fake Speckle"},
        "userInfo": {"id": "fake-user", "name": "Fake User", "email": "user@example.com"},
    }
    (folder / f"{token}.json").write_text(json.dumps(account))


def bundle_reference(model_id: str, version_id: str) -> str:
    return f"bundle.{PROJECT}.{model_id}.{version_id}"


PROJECT = "461cc2a20f"
"""The Speckle project of the Revit Advanced Sample versions."""


def test_without_a_local_account_there_is_no_local_client(accounts):
    assert server.local_client("https://app.speckle.systems") is None


def test_the_local_account_signs_in(fake, accounts):
    add_account(accounts, fake.url, fake.token)
    client = server.local_client(fake.url)
    assert client is not None
    assert client.account.token == fake.token
    assert client.url == fake.url


def test_an_account_the_server_refuses_is_passed_over(fake, accounts):
    add_account(accounts, fake.url, "expired", default=True)
    assert server.local_client(fake.url) is None
    add_account(accounts, fake.url, fake.token)
    client = server.local_client(fake.url)
    assert client is not None
    assert client.account.token == fake.token


@pytest.mark.parametrize("expired_first", [True, False])
def test_every_account_of_a_user_is_tried(fake, accounts, monkeypatch, expired_first):
    # specklepy's get_accounts_for_server keeps the first account of each user in the
    # folder's listing order, which made the test above fail on CI
    add_account(accounts, fake.url, "expired")
    add_account(accounts, fake.url, fake.token)
    listing = sorted(path.name for path in accounts.iterdir())
    listing.sort(key=lambda name: name.startswith("expired"), reverse=expired_first)
    listdir = os.listdir
    monkeypatch.setattr(
        os, "listdir", lambda path: listing if Path(path) == accounts else listdir(path)
    )
    client = server.local_client(fake.url)
    assert client is not None
    assert client.account.token == fake.token


def test_an_account_of_another_server_is_not_used(fake, accounts):
    add_account(accounts, "https://speckle.example.com", fake.token)
    assert server.local_client(fake.url) is None


def test_a_stored_account_signs_in_at_its_own_url(fake, accounts):
    add_account(accounts, fake.url, fake.token)
    # https by default, but the account was stored for the fake's http
    client = server.local_client(fake.url.removeprefix("http://"))
    assert client is not None
    assert client.url == fake.url


def test_a_stored_https_token_never_goes_over_http(fake, accounts):
    add_account(accounts, fake.url.replace("http://", "https://"), fake.token)
    # the fake speaks http only, so the stored https URL cannot reach it
    with pytest.raises(SpeckleException):
        server.local_client(fake.url)
    assert not any(authorized for _, _, authorized in fake.requests)


def test_a_graphql_refusal_passes_an_account_over_and_other_errors_raise(fake, accounts):
    fake.graphql_errors = {"forbidden": "FORBIDDEN", "broken": "INTERNAL_SERVER_ERROR"}
    add_account(accounts, fake.url, "forbidden")
    assert server.local_client(fake.url) is None
    add_account(accounts, fake.url, "broken", default=True)
    with pytest.raises(SpeckleException, match="INTERNAL_SERVER_ERROR"):
        server.local_client(fake.url)


def test_a_token_signs_in(fake):
    with warnings.catch_warnings():
        # http to this machine is no reason to warn
        warnings.simplefilter("error", UserWarning)
        client = server.token_client(fake.token, fake.url)
    assert client.account.userInfo.name == "Fake User"
    with pytest.raises(ValueError, match="refuses the token"):
        server.token_client("wrong", fake.url)


def test_a_token_over_plain_http_to_another_machine_warns(monkeypatch):
    # stop before any request: the warning comes first
    monkeypatch.setattr(server.SpeckleClient, "authenticate_with_token", lambda self, token: None)
    with pytest.warns(UserWarning, match="unencrypted"), pytest.raises(ValueError):
        server.token_client("token", "http://speckle.example.com")


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("localhost", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("speckle.example.com", False),
        ("10.0.0.1", False),
        (None, False),
    ],
)
def test_loopback_hosts(host, loopback):
    assert server._is_loopback(host) is loopback


@pytest.mark.parametrize(
    ("given", "url"),
    [
        ("app.speckle.systems", "https://app.speckle.systems"),
        ("https://app.speckle.systems/projects/461cc2a20f", "https://app.speckle.systems"),
        ("http://localhost:3000/", "http://localhost:3000"),
    ],
)
def test_a_server_is_its_scheme_and_host(given, url):
    assert server._server_url(given) == url


def test_receiving_a_bundle_only_version_gives_the_bucket_frame(fake, client, arch, tmp_path):
    fake.add_bundle(PROJECT, ARCH.model_id, ARCH.version_id, arch.bundle)
    fake.add_version(
        PROJECT,
        ARCH.model_id,
        bundle_reference(ARCH.model_id, ARCH.version_id),
        version_id=ARCH.version_id,
    )
    # the model's latest version
    received = server.receive(client, PROJECT, ARCH.model_id, directory=tmp_path)
    assert received.v3_route == "projected"
    assert (received.project_id, received.model_id, received.version_id) == (
        PROJECT,
        ARCH.model_id,
        ARCH.version_id,
    )
    assert received.bundle == tmp_path / ARCH.model_id / ARCH.version_id
    assert sorted(path.name for path in received.bundle.iterdir()) == sorted(
        path.name for path in arch.bundle.iterdir() if path.suffix == ".parquet"
    )
    # bundle_objects reproduces the bucket's projection, object for object but the root
    assert {o["id"] for o in received.objects[1:]} == {o["id"] for o in arch.objects[1:]}
    assert received.bimdataframe().equals(arch.frame)


def test_receiving_a_version_with_v3_objects(fake, client, arch, tmp_path):
    fake.add_objects(PROJECT, arch.objects)
    fake.add_bundle(PROJECT, ARCH.model_id, ARCH.version_id, arch.bundle)
    fake.add_version(PROJECT, ARCH.model_id, arch.objects[0]["id"], version_id=ARCH.version_id)
    received = server.receive(client, PROJECT, ARCH.model_id, ARCH.version_id, directory=tmp_path)
    assert received.v3_route == "server"
    assert received.objects[0] == arch.objects[0]
    assert sorted(received.objects[1:], key=lambda o: o["id"]) == sorted(
        arch.objects[1:], key=lambda o: o["id"]
    )
    assert received.bundle == tmp_path / ARCH.model_id / ARCH.version_id
    assert received.bimdataframe().equals(arch.frame)


def test_a_version_without_a_bundle_leaves_no_folder(fake, client, monkeypatch):
    objects = revit_like()
    # a root names its closure, which the server sends with it
    objects[0]["__closure"] = {o["id"]: 1 for o in objects[1:]}
    fake.add_objects(PROJECT, objects)
    fake.add_version(PROJECT, "model", objects[0]["id"])
    made: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def mkdtemp(**kwargs: Any) -> str:
        made.append(real_mkdtemp(**kwargs))
        return made[-1]

    monkeypatch.setattr(server.tempfile, "mkdtemp", mkdtemp)
    received = server.receive(client, PROJECT, "model")
    assert received.bundle is None
    assert received.v3_route == "server"
    assert [o["id"] for o in received.objects] == [o["id"] for o in objects]
    assert len(made) == 1
    assert not Path(made[0]).exists()


def test_a_failed_receive_removes_its_temporary_folder(fake, client, arch, monkeypatch):
    fake.add_bundle(PROJECT, ARCH.model_id, ARCH.version_id, arch.bundle)
    fake.add_version(
        PROJECT,
        ARCH.model_id,
        bundle_reference(ARCH.model_id, ARCH.version_id),
        version_id=ARCH.version_id,
    )
    made: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def mkdtemp(**kwargs: Any) -> str:
        made.append(real_mkdtemp(**kwargs))
        return made[-1]

    def projection_fails(folder: Path) -> Any:
        raise RuntimeError("projection failed")

    monkeypatch.setattr(server.tempfile, "mkdtemp", mkdtemp)
    monkeypatch.setattr(server, "bundle_objects", projection_fails)
    with pytest.raises(RuntimeError, match="projection failed"):
        server.receive(client, PROJECT, ARCH.model_id)
    assert len(made) == 1
    assert not Path(made[0]).exists()


def test_bundle_downloads_carry_no_token(fake, client, arch, tmp_path):
    fake.add_bundle(PROJECT, ARCH.model_id, ARCH.version_id, arch.bundle)
    fake.add_version(
        PROJECT,
        ARCH.model_id,
        bundle_reference(ARCH.model_id, ARCH.version_id),
        version_id=ARCH.version_id,
    )
    server.receive(client, PROJECT, ARCH.model_id, directory=tmp_path)
    listings = [authorized for _, path, authorized in fake.requests if path.endswith("artifacts")]
    downloads = [authorized for _, path, authorized in fake.requests if path.startswith("/files/")]
    assert listings == [True]
    assert len(downloads) == 18
    assert not any(downloads)


def test_no_file_holds_the_token(fake, arch, monkeypatch, tmp_path):
    for variable in ("HOME", "SPECKLE_USERDATA_PATH", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
        monkeypatch.setenv(variable, str(tmp_path / variable.lower()))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config_home"))
    (tmp_path / "tmp").mkdir()
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    fake.token = "fake-token-6b1f0c9e4d2a"
    fake.add_bundle(PROJECT, ARCH.model_id, ARCH.version_id, arch.bundle)
    fake.add_version(
        PROJECT,
        ARCH.model_id,
        bundle_reference(ARCH.model_id, ARCH.version_id),
        version_id=ARCH.version_id,
    )
    client = server.token_client(fake.token, fake.url)
    small = arch.frame.with_frame(arch.frame.frame.head(50))
    server.send(client, small, PROJECT, "sent")
    server.receive(client, PROJECT, "sent")
    received = server.receive(client, PROJECT, ARCH.model_id)
    files = [path for path in tmp_path.rglob("*") if path.is_file()]
    # the bundle went into the temporary folder, so the search covers what receive writes
    assert received.bundle is not None
    assert received.bundle.is_relative_to(tmp_path / "tmp")
    assert all(fake.token.encode() not in path.read_bytes() for path in files)


def test_a_bundle_only_version_without_its_bundle_raises(fake, client, tmp_path):
    fake.add_version(PROJECT, "model", bundle_reference("model", "v1"), version_id="v1")
    with pytest.raises(ValueError, match="exists only as a bundle"):
        server.receive(client, PROJECT, "model", directory=tmp_path)


def test_a_model_without_versions_raises(fake, client):
    with pytest.raises(ValueError, match="has no version"):
        server.receive(client, PROJECT, "empty")


def test_a_sent_bimdataframe_comes_back(fake, client, arch):
    version_id = server.send(client, arch.frame, PROJECT, "sent", message="round trip")
    (version,) = fake.versions[(PROJECT, "sent")]
    assert version["id"] == version_id
    assert (version["message"], version["sourceApplication"]) == ("round trip", "specklewidgets")
    received = server.receive(client, PROJECT, "sent")
    assert received.version_id == version_id
    assert received.v3_route == "server"
    assert received.bundle is None
    assert received.objects[0]["id"] == version["referencedObject"]
    back = received.bimdataframe()
    assert_kept(arch.frame, back)
    # container comes back as a field of the object, not as the column, and the levels,
    # which have no mesh, are not sent: read_speckle sets container from a bundle only
    assert back.frame["container"].null_count() == len(back)
    assert not back.frame.filter(pl.col("class") == "Levels").height
    containers = back.frame.select(
        "id", pl.col("properties").struct.field("object").struct.field("container")
    )
    sent = arch.frame.frame.join(back.frame.select("id"), on="id").select("id", "container")
    assert dict(containers.drop_nulls().iter_rows()) == dict(sent.drop_nulls().iter_rows())


def test_send_and_receive_keep_specklepy_deprecations_to_themselves(fake, client, arch):
    small = arch.frame.with_frame(arch.frame.frame.head(50))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        server.send(client, small, PROJECT, "sent")
        server.receive(client, PROJECT, "sent")


def test_sending_needs_a_token_the_server_takes(fake, client, arch):
    client.account.token = "revoked"
    small = arch.frame.with_frame(arch.frame.frame.head(50))
    with pytest.raises(SpeckleException, match="Invalid credentials"):
        server.send(client, small, PROJECT, "sent")
    assert (PROJECT, "sent") not in fake.versions
