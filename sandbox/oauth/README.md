# Speckle OAuth widget (sandbox)

The first stab at signing in to a Speckle server from a notebook, moved here from the old
`speckle_widgets` package when `specklewidgets` replaced it. It is not packaged.

- `auth.py`: `SpeckleAuthWidget`, which loads `auth.js` as it is (no build step).
- `auth.js`: opens a popup to `{server_url}/authn/verify/{app_id}/{challenge}`, takes the
  access code that `callback.html` posts back, exchanges it for a token at
  `{server_url}/auth/token` and reads the user's name.
- `callback.html`: the OAuth redirect page. Host it on GitHub Pages and register its URL as a
  redirect URI of your Speckle app.
- `demo.py`: a marimo notebook with the widget; run it from this folder,
  `uv run marimo edit demo.py`.
