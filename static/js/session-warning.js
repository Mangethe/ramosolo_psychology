(() => {
  const dialog = document.getElementById("session-warning");
  if (!dialog) return;
  const title = document.getElementById("session-warning-title");
  const message = document.getElementById("session-warning-message");
  const countdown = document.getElementById("session-warning-clock");
  const stay = document.getElementById("session-stay");
  const logout = document.getElementById("session-logout");
  const login = document.getElementById("session-login");
  const help = document.getElementById("session-warning-help");
  const root = document.documentElement;
  const tabs = "BroadcastChannel" in window ? new BroadcastChannel("ramosolo-session") : null;
  let wall = performance.timeOrigin;
  let monotonic = 0;
  let remaining = Number(dialog.dataset.remaining) * 1000;
  let absolute = Number(dialog.dataset.absolute) * 1000;
  let warning = Number(dialog.dataset.warning);
  let ended = false;
  let pending = false;
  let serial = 0;
  let lastActivity = Date.now();
  let page = dialog.dataset.page;

  function show() {
    if (!dialog.open) dialog.showModal();
  }

  function finish(changed = false) {
    if (ended) return;
    ended = true;
    if (dialog.open) dialog.close();
    document.body.replaceChildren(dialog);
    document.title = "Sign in again · Ramosolo";
    history.replaceState(null, "", dialog.dataset.login);
    root.classList.remove("session-screen-locked");
    root.classList.add("session-screen-ended");
    title.textContent = changed ? "Your session has changed" : "Your session has ended";
    help.textContent = "The previous page and its unsaved changes were cleared.";
    message.textContent = "Sign in again to load fresh records you are authorised to view.";
    countdown.textContent = "0:00";
    stay.hidden = true;
    logout.hidden = true;
    login.hidden = false;
    show();
    login.focus();
  }

  async function check(extend = false) {
    if (ended || pending) return;
    const checkId = ++serial;
    const requestWall = Date.now();
    const requestMono = performance.now();
    if (extend) {
      pending = true;
      stay.disabled = true;
    }
    try {
      const options = extend ? {
        method: "POST", headers: {"X-CSRFToken": dialog.dataset.csrf}, keepalive: true
      } : {};
      const response = await fetch(extend ? dialog.dataset.extend : dialog.dataset.status,
        {...options, cache: "no-store", redirect: "error"});
      if (checkId !== serial || ended) return;
      if (response.status === 401) {
        finish();
        return;
      }
      if (!response.ok) throw new Error();
      const state = await response.json();
      if (checkId !== serial || ended) return;
      if (page && state.page !== page) {
        finish(true);
        return;
      }
      page = state.page;
      wall = requestWall;
      monotonic = requestMono;
      remaining = (state.expires_at - state.now) * 1000;
      absolute = (state.absolute_at - state.now) * 1000;
      warning = state.warning_seconds;
      root.classList.remove("session-screen-locked");
      message.textContent = "";
      if (extend) {
        lastActivity = Date.now();
        tabs?.postMessage("changed");
      }
      tick();
    } catch {
      if (checkId === serial && (extend || dialog.open)) {
        message.textContent = "The server did not confirm your session. Try again.";
      }
    } finally {
      if (extend) {
        pending = false;
        stay.disabled = false;
      }
    }
  }

  function tick() {
    if (ended) return;
    const elapsed = Math.max(Date.now() - wall, performance.now() - monotonic);
    const seconds = Math.ceil((remaining - elapsed) / 1000);
    if (seconds <= 0) {
      finish();
      return;
    }
    if (seconds > warning) {
      if (dialog.open) dialog.close();
      return;
    }
    countdown.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
    stay.hidden = absolute <= remaining;
    if (stay.hidden) title.textContent = "Your maximum sign-in time is approaching";
    else title.textContent = "Your session is about to end";
    show();
  }

  async function signOut(leavePage = false) {
    if (pending || ended) return;
    pending = true;
    ++serial;
    try {
      const response = await fetch(dialog.dataset.logout, {method: "POST",
        headers: {"X-CSRFToken": dialog.dataset.csrf, "Accept": "application/json"}, redirect: "error"});
      if (response.status !== 204) throw new Error();
      tabs?.postMessage("changed");
      finish();
      if (leavePage) window.location.replace(dialog.dataset.home);
    } catch {
      message.textContent = "The server did not confirm logout. Try again.";
      show();
    } finally {
      pending = false;
    }
  }

  dialog.addEventListener("cancel", event => event.preventDefault());
  stay.addEventListener("click", () => check(true));
  logout.addEventListener("click", () => signOut());
  function deliberateActivity(event) {
    if (event.isTrusted && !event.repeat && !document.hidden && !dialog.open &&
        Date.now() - lastActivity >= 60000) {
      lastActivity = Date.now();
      check(true);
    }
  }
  document.addEventListener("pointerdown", deliberateActivity);
  document.addEventListener("keydown", deliberateActivity);
  document.addEventListener("submit", event => {
    const form = event.target;
    if (form instanceof HTMLFormElement &&
        new URL(form.action).pathname === dialog.dataset.logout) {
      event.preventDefault();
      signOut(true);
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (ended) return;
    root.classList.add("session-screen-locked");
    if (!document.hidden) {
      tick();
      check();
    }
  });
  window.addEventListener("pagehide", () => root.classList.add("session-screen-locked"));
  window.addEventListener("pageshow", () => {
    tick();
    check();
  });
  if (tabs) tabs.onmessage = () => check();
  for (const field of document.querySelectorAll("main form, main textarea, main input:not([type='password'])")) {
    if (field.getAttribute("autocomplete") !== "one-time-code") field.setAttribute("autocomplete", "off");
  }
  setInterval(tick, 250);
  setInterval(() => check(), 20000);
  tick();
  check();
})();
