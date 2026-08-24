/* Minimal offline shell — API calls still need the host online. */
const CACHE = "careerpilot-remote-v1";
const ASSETS = ["./", "index.html", "styles.css", "app.js", "manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/remote")) {
    return; // network only for API
  }
  event.respondWith(
    caches.match(event.request).then((hit) => hit || fetch(event.request))
  );
});
