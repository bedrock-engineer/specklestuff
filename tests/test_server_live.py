"""Receive and send against a real Speckle server, with this machine's Speckle account.

Marked ``live``, so ``uv run pytest`` leaves them out: ``uv run pytest -m live`` runs them.
Each skips when the machine has no Speckle account for its server (Speckle Manager's or a
connector's, as specklepy's ``get_local_accounts`` finds them), so CI, which has none and gets
no token, skips them even with ``-m live``.

- Receiving reads the Revit Advanced Sample's architectural version from app.speckle.systems
  (the server and project the bimpolars bucket names) and compares it with the bucket's frame.
- The round trip sends the structural version's BimDataFrame to the server named by
  ``SPECKLEWIDGETS_TEST_SERVER`` (app.speckle.systems by default), into a new model of the
  project ``SPECKLEWIDGETS_TEST_PROJECT``, or of a new private project when that is not set;
  it deletes the model, or the project it made, afterwards.
"""

import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

pytestmark = pytest.mark.live

data = pytest.importorskip("bimpolars.data")
server = pytest.importorskip("specklewidgets.server")
from specklepy.api.enums import ProjectVisibility  # noqa: E402
from specklepy.api.inputs.model_inputs import CreateModelInput, DeleteModelInput  # noqa: E402
from specklepy.api.inputs.project_inputs import ProjectCreateInput  # noqa: E402
from specklepy.logging.exceptions import SpeckleException  # noqa: E402

from round_trip import assert_kept, bucket_version  # noqa: E402

SERVER_ENV = "SPECKLEWIDGETS_TEST_SERVER"
"""The server the round trip sends to; app.speckle.systems by default."""

PROJECT_ENV = "SPECKLEWIDGETS_TEST_PROJECT"
"""The project the round trip makes its model in; a new private project by default."""


def signed_in(url: str) -> Any:
    client = server.local_client(url)
    if client is None:
        pytest.skip(f"this machine has no Speckle account for {url} whose token works")
    return client


@contextmanager
def scratch_project(client: Any) -> Iterator[str]:
    """The project of SPECKLEWIDGETS_TEST_PROJECT, or a new private one, deleted afterwards."""
    project_id = os.environ.get(PROJECT_ENV)
    if project_id:
        yield project_id
        return
    if not client.active_user.can_create_personal_projects().authorized:
        pytest.skip(f"the account cannot make a personal project: set {PROJECT_ENV}")
    project = client.project.create(
        ProjectCreateInput(
            name=f"specklewidgets test {secrets.token_hex(3)}",
            description="Made and deleted by specklewidgets' tests/test_server_live.py",
            visibility=ProjectVisibility.PRIVATE,
        )
    )
    try:
        yield project.id
    finally:
        client.project.delete(project.id)


def test_receiving_the_arch_version_gives_the_bucket_frame(tmp_path):
    arch = bucket_version(data.RVT_SPECKLE_ARCH)
    client = signed_in(arch.server)
    try:
        client.project.get(arch.project_id)
    except SpeckleException:
        pytest.skip(f"the account cannot read the project {arch.project_id} on {arch.server}")
    received = server.receive(
        client, arch.project_id, arch.model_id, arch.version_id, directory=tmp_path
    )
    assert received.v3_route == "projected"
    assert received.bundle == tmp_path / arch.model_id / arch.version_id
    assert received.bimdataframe().equals(arch.frame)


def test_a_sent_bimdataframe_comes_back():
    structural = bucket_version(data.RVT_SPECKLE_STR)
    client = signed_in(os.environ.get(SERVER_ENV, server.DEFAULT_SERVER))
    with scratch_project(client) as project_id:
        model = client.model.create(
            CreateModelInput(
                name=f"specklewidgets-test-{secrets.token_hex(3)}",
                description="Made and deleted by specklewidgets' tests/test_server_live.py",
                project_id=project_id,
            )
        )
        try:
            version_id = server.send(
                client, structural.frame, project_id, model.id, message="round trip"
            )
            received = server.receive(client, project_id, model.id)
            assert received.version_id == version_id
            assert_kept(structural.frame, received.bimdataframe())
        finally:
            client.model.delete(DeleteModelInput(id=model.id, project_id=project_id))
