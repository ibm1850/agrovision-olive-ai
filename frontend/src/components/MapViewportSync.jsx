import { useEffect } from "react";
import { useMap } from "react-leaflet";

export default function MapViewportSync({ center, zoom }) {
  const map = useMap();
  const lat = Array.isArray(center) ? Number(center[0]) : NaN;
  const lng = Array.isArray(center) ? Number(center[1]) : NaN;

  useEffect(() => {
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const target = [lat, lng];
    map.setView(target, zoom ?? map.getZoom(), { animate: false });
    const timer = window.setTimeout(() => {
      map.invalidateSize();
    }, 40);
    return () => window.clearTimeout(timer);
  }, [map, lat, lng, zoom]);

  return null;
}

