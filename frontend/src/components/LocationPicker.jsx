import { CircleMarker, useMapEvents } from "react-leaflet";

export default function LocationPicker({ value, onChange }) {
  useMapEvents({
    click(event) {
      onChange([
        Number(event.latlng.lat.toFixed(6)),
        Number(event.latlng.lng.toFixed(6)),
      ]);
    },
  });

  if (!Array.isArray(value) || value.length !== 2) return null;
  return <CircleMarker center={value} radius={8} pathOptions={{ color: "#2f7c2d", fillOpacity: 0.9 }} />;
}
