const CACHE_NAME = "gravity-os-offline-v1";
const OFFLINE_URL = "/offline.html";
const SAFE_ASSETS = [OFFLINE_URL, "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SAFE_ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("gravity-os-offline-") && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Never intercept API calls, mutations, authenticated data requests, or
  // static assets. Navigations stay network-only and receive a simple offline
  // page only when the network itself is unavailable.
  if (request.mode !== "navigate" || request.method !== "GET") {
    return;
  }

  event.respondWith(
    fetch(request).catch(async () => {
      const offlineResponse = await caches.match(OFFLINE_URL);
      return offlineResponse || Response.error();
    }),
  );
});
