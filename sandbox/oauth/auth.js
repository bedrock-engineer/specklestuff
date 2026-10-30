/**
 * SpeckleAuthWidget front-end module.
 *
 * OAuth flow:
 * 1. Generate a random challenge string
 * 2. Open a popup to {server_url}/authn/verify/{app_id}/{challenge}
 * 3. After login, Speckle redirects the popup to callback_url?access_code=...
 * 4. callback.html calls window.opener.postMessage({ access_code, challenge })
 * 5. Exchange access_code + challenge for token via POST {server_url}/auth/token
 * 6. Fetch user info via GraphQL
 */

function generateChallenge() {
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
}

const ACTIVE_USER_QUERY = `
  query {
    activeUser {
      id
      name
    }
  }
`;

export function render({ model, el }) {
  let popup = null;
  let currentChallenge = null;
  let messageListener = null;

  // ── Styles ──────────────────────────────────────────────────────────────────
  const style = document.createElement("style");
  style.textContent = `
    .speckle-auth {
      font-family: system-ui, -apple-system, sans-serif;
      padding: 12px 16px;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      background: #ffffff;
      max-width: 360px;
    }
    .speckle-auth h3 {
      margin: 0 0 12px 0;
      font-size: 14px;
      font-weight: 600;
      color: #1a202c;
    }
    .speckle-auth button {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: opacity 0.15s;
    }
    .speckle-auth button:hover { opacity: 0.85; }
    .speckle-auth button:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-signin {
      background: #3b82f6;
      color: #ffffff;
    }
    .btn-signout {
      background: #f1f5f9;
      color: #374151;
      margin-top: 8px;
    }
    .speckle-auth .user-info {
      font-size: 13px;
      color: #374151;
      margin-bottom: 4px;
    }
    .speckle-auth .error {
      font-size: 13px;
      color: #dc2626;
      margin-top: 8px;
      padding: 6px 10px;
      background: #fef2f2;
      border-radius: 4px;
    }
    .speckle-auth .loading {
      font-size: 13px;
      color: #6b7280;
      margin-top: 4px;
    }
  `;
  el.appendChild(style);

  // ── Root container ───────────────────────────────────────────────────────────
  const root = document.createElement("div");
  root.className = "speckle-auth";
  el.appendChild(root);

  // ── Render helpers ────────────────────────────────────────────────────────────
  function setError(msg) {
    model.set("error_message", msg);
    model.save_changes();
  }

  function clearError() {
    model.set("error_message", "");
    model.save_changes();
  }

  function setAuthenticated(token, refreshToken, userId, userName) {
    model.set("token", token);
    model.set("refresh_token", refreshToken);
    model.set("user_id", userId);
    model.set("user_name", userName);
    model.set("is_authenticated", true);
    model.set("error_message", "");
    model.save_changes();
  }

  function resetAuth() {
    model.set("token", "");
    model.set("refresh_token", "");
    model.set("user_id", "");
    model.set("user_name", "");
    model.set("is_authenticated", false);
    model.save_changes();
  }

  // ── DOM update ────────────────────────────────────────────────────────────────
  function renderUI() {
    root.innerHTML = "";

    const title = document.createElement("h3");
    title.textContent = "Speckle Authentication";
    root.appendChild(title);

    const isAuthenticated = model.get("is_authenticated");
    const errorMessage = model.get("error_message");

    if (isAuthenticated) {
      const info = document.createElement("div");
      info.className = "user-info";
      info.textContent = `Signed in as ${model.get("user_name")}`;
      root.appendChild(info);

      const signOutBtn = document.createElement("button");
      signOutBtn.className = "btn-signout";
      signOutBtn.textContent = "Sign out";
      signOutBtn.addEventListener("click", handleSignOut);
      root.appendChild(signOutBtn);
    } else {
      const signInBtn = document.createElement("button");
      signInBtn.className = "btn-signin";
      signInBtn.textContent = "Sign in to Speckle";
      signInBtn.addEventListener("click", handleSignIn);
      root.appendChild(signInBtn);
    }

    if (errorMessage) {
      const errorEl = document.createElement("div");
      errorEl.className = "error";
      errorEl.textContent = errorMessage;
      root.appendChild(errorEl);
    }
  }

  // ── Sign-in flow ──────────────────────────────────────────────────────────────
  async function handleSignIn() {
    clearError();

    const serverUrl = model.get("server_url");
    const appId = model.get("app_id");
    const appSecret = model.get("app_secret");
    const callbackUrl = model.get("callback_url");

    if (!appId) {
      setError("app_id is not set.");
      return;
    }
    if (!appSecret) {
      setError("app_secret is not set.");
      return;
    }
    if (!callbackUrl) {
      setError("callback_url is not set.");
      return;
    }

    currentChallenge = generateChallenge();

    // Clean up any previous listener
    if (messageListener) {
      window.removeEventListener("message", messageListener);
    }

    // Register message listener BEFORE opening popup
    messageListener = async (event) => {
      const { access_code, challenge } = event.data || {};
      if (!access_code || !challenge) return;

      if (challenge !== currentChallenge) {
        setError("Challenge mismatch — possible CSRF. Please try again.");
        resetAuth();
        return;
      }

      window.removeEventListener("message", messageListener);
      messageListener = null;

      // Show loading state
      root.innerHTML = "";
      const title = document.createElement("h3");
      title.textContent = "Speckle Authentication";
      const loading = document.createElement("div");
      loading.className = "loading";
      loading.textContent = "Signing in...";
      root.appendChild(title);
      root.appendChild(loading);

      try {
        // Exchange access_code for token
        const tokenRes = await fetch(`${serverUrl}/auth/token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            appId,
            appSecret,
            accessCode: access_code,
            challenge,
          }),
        });

        if (!tokenRes.ok) {
          throw new Error(`Token exchange failed: ${tokenRes.status} ${tokenRes.statusText}`);
        }

        const tokenData = await tokenRes.json();
        if (tokenData.err) {
          throw new Error(tokenData.err);
        }

        const { token, refreshToken } = tokenData;

        // Fetch user info
        const userRes = await fetch(`${serverUrl}/graphql`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify({ query: ACTIVE_USER_QUERY }),
        });

        if (!userRes.ok) {
          throw new Error(`User fetch failed: ${userRes.status}`);
        }

        const userData = await userRes.json();
        const activeUser = userData?.data?.activeUser;

        if (!activeUser) {
          throw new Error("Could not retrieve user info.");
        }

        setAuthenticated(token, refreshToken || "", activeUser.id, activeUser.name);
      } catch (err) {
        setError(err.message || "Authentication failed.");
        resetAuth();
      }

      renderUI();
    };

    window.addEventListener("message", messageListener);

    // Open popup
    const authUrl = `${serverUrl}/authn/verify/${appId}/${currentChallenge}`;
    popup = window.open(authUrl, "speckle-auth", "width=500,height=700,resizable=yes");

    if (!popup || popup.closed || typeof popup.closed === "undefined") {
      window.removeEventListener("message", messageListener);
      messageListener = null;
      setError("Popup was blocked. Please allow popups for this site and try again.");
      renderUI();
    }
  }

  // ── Sign-out ──────────────────────────────────────────────────────────────────
  function handleSignOut() {
    resetAuth();
    renderUI();
  }

  // ── Reactivity ────────────────────────────────────────────────────────────────
  model.on("change:is_authenticated", renderUI);
  model.on("change:error_message", renderUI);
  model.on("change:user_name", renderUI);

  // Initial render
  renderUI();

  // ── Cleanup ───────────────────────────────────────────────────────────────────
  return () => {
    if (messageListener) {
      window.removeEventListener("message", messageListener);
    }
    if (popup && !popup.closed) {
      popup.close();
    }
  };
}
