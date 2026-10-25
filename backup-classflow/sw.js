self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  e.respondWith(fetch(e.request).catch(function () {
    if (e.request.mode === "navigate") {
      return new Response("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><body style='font-family:sans-serif;text-align:center;padding:40px'><h2>You are offline</h2><p>Please connect to the internet and try again.</p></body>", { headers: { "Content-Type": "text/html" } });
    }
    return Response.error();
  }));
});
