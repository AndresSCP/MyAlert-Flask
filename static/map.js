(() => {
  const container = document.getElementById("map");
  const status = document.getElementById("map-status");
  if (!container) return;
  if (!window.L) {
    status.textContent = "El mapa no está disponible.";
    return;
  }

  const map = L.map(container).setView([-32.88, -71.25], 13);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map).on("tileerror", () => {
    status.textContent = "No se pudieron cargar algunas imágenes del mapa.";
  });

  const pins = document.getElementById("pins");
  if (pins) {
    const points = JSON.parse(pins.textContent);
    const group = L.featureGroup().addTo(map);
    for (const point of points) {
      const popup = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = point.title;
      popup.append(title, document.createElement("br"), point.place);
      L.marker([point.lat, point.lon]).bindPopup(popup).addTo(group);
    }
    if (points.length) map.fitBounds(group.getBounds(), { padding: [28, 28], maxZoom: 15 });
    return;
  }

  const lat = document.getElementById("lat");
  const lon = document.getElementById("lon");
  const clear = document.getElementById("clear-pin");
  let marker;

  function updatePin() {
    const latitude = lat.valueAsNumber;
    const longitude = lon.valueAsNumber;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) ||
        Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
      if (marker) marker.remove();
      marker = undefined;
      return;
    }
    if (marker) {
      marker.setLatLng([latitude, longitude]);
    } else {
      marker = L.marker([latitude, longitude]).addTo(map);
    }
    map.panTo([latitude, longitude]);
  }

  map.on("click", ({ latlng }) => {
    const point = latlng.wrap();
    lat.value = point.lat.toFixed(6);
    lon.value = point.lng.toFixed(6);
    updatePin();
  });
  lat.addEventListener("change", updatePin);
  lon.addEventListener("change", updatePin);
  clear.addEventListener("click", () => {
    lat.value = "";
    lon.value = "";
    updatePin();
  });
  updatePin();
})();
