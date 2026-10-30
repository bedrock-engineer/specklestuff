"""Speckle OAuth in a notebook: the first stab, kept as a sandbox and not packaged.

``auth.js`` opens a popup to the Speckle server, ``callback.html`` (hosted on GitHub Pages and
registered as the Speckle app's redirect URI) posts the access code back, and the widget
exchanges it for a token. See ``demo.py``.
"""

from pathlib import Path

import anywidget
import traitlets


class SpeckleAuthWidget(anywidget.AnyWidget):
    """Signs in to a Speckle server with OAuth and holds the token."""

    _esm = Path(__file__).with_name("auth.js")

    server_url = traitlets.Unicode("https://app.speckle.systems").tag(sync=True)
    app_id = traitlets.Unicode("").tag(sync=True)
    app_secret = traitlets.Unicode("").tag(sync=True)
    callback_url = traitlets.Unicode("").tag(sync=True)  # GitHub Pages URL — user must set
    token = traitlets.Unicode("").tag(sync=True)
    refresh_token = traitlets.Unicode("").tag(sync=True)
    is_authenticated = traitlets.Bool(False).tag(sync=True)
    user_name = traitlets.Unicode("").tag(sync=True)
    user_id = traitlets.Unicode("").tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)
