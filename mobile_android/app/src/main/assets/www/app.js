(() => {
  const TOKEN_KEY = "careerpilot_remote_token";
  const SERVER_KEY = "careerpilot_remote_server";
  const $ = (id) => document.getElementById(id);
  const logEl = () => $("log");

  function needsManualServer() {
    const path = window.location.pathname || "";
    const proto = window.location.protocol || "";
    if (typeof window.Capacitor !== "undefined") return true;
    if (proto === "capacitor:" || proto === "file:") return true;
    if (path.includes("/m") && (proto === "http:" || proto === "https:")) return false;
    return true;
  }

  function defaultServer() {
    const stored = localStorage.getItem(SERVER_KEY) || "";
    if (stored) return stored;
    if (!needsManualServer()) return window.location.origin;
    return "";
  }

  function normalizeServer(raw) {
    let s = (raw || "").trim().replace(/\/+$/, "");
    if (!s) return "";
    if (!/^https?:\/\//i.test(s)) s = `http://${s}`;
    return s.replace(/\/+$/, "");
  }

  function apiBase() {
    const fromInput = normalizeServer($("server") && $("server").value);
    if (fromInput) return fromInput;
    const stored = normalizeServer(localStorage.getItem(SERVER_KEY) || "");
    if (stored) return stored;
    if (/^https?:$/.test(window.location.protocol) && (window.location.pathname || "").includes("/m")) {
      return window.location.origin;
    }
    return "";
  }

  function token() {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(v) {
    if (v) {
      localStorage.setItem(TOKEN_KEY, v);
      sessionStorage.setItem(TOKEN_KEY, v);
    } else {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    }
  }

  function setServer(v) {
    const n = normalizeServer(v);
    if (n) localStorage.setItem(SERVER_KEY, n);
    else localStorage.removeItem(SERVER_KEY);
    if ($("server")) $("server").value = n;
  }

  function headers() {
    const t = token();
    return {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${t}`,
      "X-Remote-Token": t,
    };
  }

  function log(msg) {
    const el = logEl();
    const line = `[${new Date().toLocaleTimeString()}] ${msg}`;
    el.textContent = `${line}\n${el.textContent || ""}`.slice(0, 8000);
  }

  async function api(path, opts = {}) {
    const base = apiBase();
    if (!base) throw new Error("Set the CareerPilot server URL first (e.g. http://192.168.1.10:8000)");
    const res = await fetch(`${base}${path}`, {
      ...opts,
      headers: { ...headers(), ...(opts.headers || {}) },
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = { detail: await res.text() };
    }
    if (!res.ok) {
      const detail = data?.detail || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function showApp(on) {
    $("login").classList.toggle("hidden", on);
    $("app").classList.toggle("hidden", !on);
  }

  async function refreshStatus() {
    const st = await api("/remote/status");
    $("toggle-scan").checked = !!st.daily_scan_enabled;
    const next = st.scheduler?.next_run || "—";
    const run = (st.recent_runs && st.recent_runs[0]) || null;
    $("status-box").innerHTML = `
      <p><strong>v${st.version}</strong> · profile ${st.profile_id ?? "none"}</p>
      <p>Server: ${apiBase()}</p>
      <p>Daily scan: <strong>${st.daily_scan_enabled ? "on" : "off"}</strong>
         · next ${next}</p>
      <p>Notifier: ${st.notifier_backend || "local"}</p>
      <p>Latest run: ${run ? `#${run.id || run.run_id} · ${run.status}` : "none"}</p>
      <p class="sub">${st.note || ""}</p>
    `;
    return st;
  }

  // Prefill server field
  if ($("server")) {
    $("server").value = defaultServer();
    const hint = $("server-hint");
    if (hint) {
      hint.textContent = needsManualServer()
        ? "APK: enter your PC URL (LAN or Tailscale), e.g. http://192.168.1.10:8000"
        : "Usually leave as-is when opened from /m/ on the same host.";
    }
  }

  $("btn-save").onclick = async () => {
    const t = $("token").value.trim();
    const server = normalizeServer($("server") ? $("server").value : "");
    $("login-msg").textContent = "";
    if (!server) {
      $("login-msg").textContent = "Enter the CareerPilot server URL (host:8000)";
      return;
    }
    if (!t) {
      $("login-msg").textContent = "Paste the REMOTE_API_TOKEN from the host .env";
      return;
    }
    setServer(server);
    setToken(t);
    try {
      await api("/remote/ping");
      showApp(true);
      await refreshStatus();
      log("Connected to " + apiBase());
    } catch (e) {
      setToken("");
      $("login-msg").textContent = e.message || String(e);
    }
  };

  $("btn-logout").onclick = () => {
    setToken("");
    showApp(false);
    $("token").value = "";
  };

  $("btn-refresh").onclick = async () => {
    try {
      await refreshStatus();
      log("Status refreshed.");
    } catch (e) {
      log(`Error: ${e.message}`);
    }
  };

  $("btn-run").onclick = async () => {
    try {
      const body = {
        top_n: 10,
        scrape_limit: 80,
        send_digest: $("toggle-notify").checked ? true : null,
      };
      const r = await api("/remote/pipeline/run", {
        method: "POST",
        body: JSON.stringify(body),
      });
      log(`Pipeline started run_id=${r.run_id} (host is working).`);
      await refreshStatus();
    } catch (e) {
      log(`Run failed: ${e.message}`);
    }
  };

  $("btn-digests").onclick = async () => {
    try {
      const r = await api("/remote/digests/latest?limit=3");
      const digests = r.digests || [];
      if (!digests.length) {
        log("No digests yet.");
        return;
      }
      digests.forEach((d) => {
        log(`--- ${d.filename} ---\n${(d.preview || "").slice(0, 600)}`);
      });
    } catch (e) {
      log(`Digests failed: ${e.message}`);
    }
  };

  $("btn-scan").onclick = async () => {
    try {
      const r = await api("/remote/settings", {
        method: "PATCH",
        body: JSON.stringify({ daily_scan_enabled: $("toggle-scan").checked }),
      });
      log(`Daily scan → ${r.daily_scan_enabled} (${r.scheduler_action})`);
      await refreshStatus();
    } catch (e) {
      log(`Settings failed: ${e.message}`);
    }
  };

  $("btn-notify").onclick = async () => {
    try {
      const r = await api("/remote/settings", {
        method: "PATCH",
        body: JSON.stringify({
          notify_on_manual_run: $("toggle-notify").checked,
        }),
      });
      log(`notify_on_manual_run saved (profile_updated=${r.profile_updated})`);
    } catch (e) {
      log(`Notify pref failed: ${e.message}`);
    }
  };

  // Auto-connect if token + server already stored
  if (token() && apiBase()) {
    $("token").value = token();
    if ($("server")) $("server").value = apiBase();
    showApp(true);
    refreshStatus().catch((e) => {
      log(`Auth expired or host unreachable? ${e.message}`);
      setToken("");
      showApp(false);
    });
  }
})();
