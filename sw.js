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

/* ---- push notifications ---- */
self.addEventListener("push", function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "ClassKhata", {
    body: d.body || "",
    icon: "/static/icon-192.png?v=3",
    badge: "/static/badge-96.png",
    tag: d.tag || "ck",
    renotify: !!d.tag,
    vibrate: [120, 60, 120],
    timestamp: Date.now(),
    data: { url: d.url || "/alerts" }
  }));
});
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      if ("focus" in list[i]) {
        return list[i].focus().then(function (c) { if (c && c.navigate) c.navigate(url); });
      }
    }
    return self.clients.openWindow(url);
  }));
});
