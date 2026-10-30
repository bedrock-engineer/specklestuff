import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    from bimpolars import data, read_speckle, version_objects
    from wigglystuff import EnvConfig

    from specklewidgets import SpeckleViewer
    from specklewidgets.server import DEFAULT_SERVER, local_client, receive, send, token_client

    return (
        DEFAULT_SERVER,
        EnvConfig,
        SpeckleViewer,
        data,
        local_client,
        mo,
        read_speckle,
        receive,
        send,
        token_client,
        version_objects,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Receive and send through a Speckle server

    Receives a Speckle version as its bundle and its v3 objects, reads it into a
    [bimpolars](https://github.com/bedrock-engineer/bimpolars) BimDataFrame, draws it, and
    sends the BimDataFrame back as a new version. The defaults pick the architectural model of
    Autodesk's Revit Advanced Sample Project on app.speckle.systems, the version the bimpolars
    test data comes from; it exists only as a bundle, so its v3 objects are projected from it.

    The notebook signs in with this machine's Speckle account for the server (Speckle Manager's
    or a connector's). Without one, paste a personal access token into the field below: it
    stays in this notebook's memory and is never written to disk. Setting `SPECKLE_TOKEN`
    before starting the notebook fills the field.
    """)
    return


@app.cell
def _(DEFAULT_SERVER, mo):
    server = mo.ui.text(value=DEFAULT_SERVER, label="Server", full_width=True)
    server
    return (server,)


@app.cell
def _(EnvConfig, local_client, mo, server, token_client):
    local = local_client(server.value)
    token = mo.ui.anywidget(
        EnvConfig({"SPECKLE_TOKEN": lambda _token: token_client(_token, server.value)})
    )
    None if local else mo.vstack(
        [mo.md(f"No working Speckle account for `{server.value}` here: paste a token."), token]
    )
    return local, token


@app.cell
def _(local, mo, server, token, token_client):
    mo.stop(local is None and not token.all_valid)
    client = local or token_client(token["SPECKLE_TOKEN"], server.value)
    mo.md(
        f"Signed in to `{client.url}` as **{client.account.userInfo.name}**, with "
        + ("this machine's account." if local else "the token.")
    )
    return (client,)


@app.cell
def _(data, mo):
    arch = data.RVT_SPECKLE_ARCH
    project_id = mo.ui.text(value="461cc2a20f", label="Project")
    model_id = mo.ui.text(value=arch.model_id, label="Model")
    version_id = mo.ui.text(value=arch.version_id, label="Version (empty: the latest)")
    receive_button = mo.ui.run_button(label="Receive")
    mo.hstack([project_id, model_id, version_id, receive_button], justify="start")
    return arch, model_id, project_id, receive_button, version_id


@app.cell
def _(client, mo, model_id, project_id, receive, receive_button, version_id):
    mo.stop(not receive_button.value, mo.md("Press **Receive**."))
    # The bundle goes into a temporary folder; pass directory= to keep it somewhere
    received = receive(client, project_id.value, model_id.value, version_id.value or None)
    bdf = received.bimdataframe()
    mo.md(
        f"Version `{received.version_id}`: {len(received.objects):,} v3 objects "
        + ("projected from its bundle" if received.v3_route == "projected" else "from the server")
        + (f", the bundle in `{received.bundle}`" if received.bundle else ", no bundle")
        + f"; {len(bdf):,} rows."
    )
    return bdf, received


@app.cell
def _(SpeckleViewer, mo, received):
    mo.ui.anywidget(SpeckleViewer(received.objects, height=500))
    return


@app.cell
def _(arch, bdf, data, mo, read_speckle, received, version_objects):
    # The bimpolars test data of this version: fetch downloads it from the bimpolars bucket on
    # first use, or finds it in BIMPOLARS_DATA_DIR
    mo.stop(received.version_id != arch.version_id)
    bucket = read_speckle(
        version_objects(data.fetch(data.RVT_SPECKLE_V3_OBJECTS), arch.version_id),
        data.fetch_bundle(arch.bundle),
    )
    mo.md(
        "The same BimDataFrame as the bimpolars test data: "
        f"**{'yes' if bdf.equals(bucket) else 'no'}**."
    )
    return


@app.cell
def _(mo, project_id):
    target_project = mo.ui.text(value=project_id.value, label="Send to project")
    target_model = mo.ui.text(label="Model id")
    message = mo.ui.text(value="Sent from specklewidgets", label="Message", full_width=True)
    send_button = mo.ui.run_button(label="Send the BimDataFrame")
    mo.vstack([mo.hstack([target_project, target_model], justify="start"), message, send_button])
    return message, send_button, target_model, target_project


@app.cell
def _(bdf, client, message, mo, send, send_button, target_model, target_project):
    mo.stop(
        not send_button.value or not target_model.value,
        mo.md("Name a model of a project you can write to, and press **Send**."),
    )
    sent = send(client, bdf, target_project.value, target_model.value, message=message.value)
    mo.md(
        f"Sent as version [`{sent}`]"
        f"({client.url}/projects/{target_project.value}/models/{target_model.value}@{sent})."
    )
    return


if __name__ == "__main__":
    app.run()
