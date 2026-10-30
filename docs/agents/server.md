# Speckle server: receive and send

`specklewidgets.server` (`local_client`, `token_client`, `receive`, `send`,
`ReceivedVersion`) talks to a Speckle server. `examples/speckle_receive_send.py` signs in,
receives a version, compares it with the bucket's frame and sends it back; it has no e2e test
(it needs a server).

## Dependencies

- It needs the extra `[server]` (`specklepy[bundle]`: its bundle download imports pyarrow) and
  `bimpolars[speckle]` (`bimpolars.bundle.bundle_objects`, the projection of a bundle-only
  version with the two fixes specklepy's `to_base` lacks; never specklepy's own
  `operations.receive` of a bundle reference, which is the plain `to_base`).
- It uses specklepy's deprecated v3 pipeline on purpose (issue #4: until Speckle opens its
  bundle code; no upstream bug reports) and silences only those DeprecationWarnings, by message
  (`server._DEPRECATIONS`); a test in `tests/test_server.py` runs a send and a receive with
  DeprecationWarnings as errors.

## Tokens

- A token is never written to disk: `token_client` keeps it in the client, `send` passes
  `use_default_cache=False` (no SQLite object cache), and the example takes it from an
  `EnvConfig` field whose validator signs in once and keeps the client
  (`test_no_file_holds_the_token` sends and receives with every home and cache folder
  redirected and searches them).
- A token goes only where it was meant to: `local_client` signs each account in at the URL
  stored with it, scheme included, never the caller's URL (it only selects the accounts by
  host); `token_client` warns on plain http to a host other than loopback; bundle files come
  from presigned URLs without the token (`test_bundle_downloads_carry_no_token`).
- `local_client` passes over an account whose token the server refuses (HTTP 401 or 403, or a
  GraphQL error whose `extensions.code` is in `server._REFUSED_CODES`) and lets other failures
  (an unreachable server, any other GraphQL error) raise. It filters `get_local_accounts()` by
  host rather than calling `get_accounts_for_server`, which keeps one account per user in
  `os.listdir` order and so may drop the user's working account.

## receive

`receive` downloads with `specklepy.bundle.download.download_bundle` (not `bundle.receive`,
whose `Model` deletes its temporary folder on close and which raises instead of answering "no
bundle"), into `<directory>/<model id>/<version id>/`, the bucket's `speckle-bundle` layout,
and does not mark the version received. A temporary folder of its own is removed again when the
receive fails or the version has no bundle. What a round trip keeps of a BimDataFrame is in
[bim.md](bim.md).

## Tests

- `tests/test_server.py` runs everything against `tests/fake_speckle_server.py`, a localhost
  server for the requests specklepy makes (GraphQL by query text, ServerTransport's REST
  routes, the `/api/v2` artifact listing). When `server.py` starts using another specklepy
  call, teach the fake its request.
- `tests/test_server_live.py` (marker `live`, deselected by `addopts`; `just live`) repeats them
  on app.speckle.systems and skips without a local account; `tests/round_trip.py` holds the
  checks both share. The live round trip deletes a scratch project it made, and the objects
  with it; in `SPECKLEWIDGETS_TEST_PROJECT` it deletes only the model and the sent objects stay.
  A delete answered with False warns with the id instead of failing.
- The cloud containers cannot reach app.speckle.systems, so the live tests have not run there
  (they skip); the fake covers the same calls offline.

Known numbers (`tests/test_server.py`, 31 tests, 38 s): receiving the bundle-only arch version
from the fake server gives the bucket's frame (`BimDataFrame.equals`), and its non-root objects
the bucket's ids; sending the arch frame (5568 drawn rows) and receiving it back keeps every
drawn row's id, class, triangles (corner by corner) and styles (name, face count, colour to
1/255), in 16 s. The live round trip sends the str frame (918 drawn rows) instead, to keep the
upload to joost's account small.
