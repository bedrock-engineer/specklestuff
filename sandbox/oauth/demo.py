import marimo

__generated_with = "0.12.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    from auth import SpeckleAuthWidget

    return SpeckleAuthWidget, mo


@app.cell
def _(SpeckleAuthWidget, mo):
    # Register an app at your Speckle server → Apps → New App
    # Set the redirect URI to your GitHub Pages callback URL.
    auth = mo.ui.anywidget(
        SpeckleAuthWidget(
            server_url="https://app.speckle.systems",
            app_id="YOUR_APP_ID",
            app_secret="YOUR_APP_SECRET",
            # Must match the redirect URI registered in your Speckle App settings.
            # Host callback.html on GitHub Pages and use its URL:
            callback_url="https://yourusername.github.io/specklestuff/callback.html",
        )
    )
    auth
    return (auth,)


@app.cell
def _(auth):
    print("Authenticated:", auth.widget.is_authenticated)
    print("User:", auth.widget.user_name)
    print("Token:", auth.widget.token[:20] + "..." if auth.widget.token else "(none)")
    return


if __name__ == "__main__":
    app.run()
