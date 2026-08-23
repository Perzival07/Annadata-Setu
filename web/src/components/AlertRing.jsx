import React from 'react';

export default function AlertRing({ feature }) {
  if (!feature) return null;

  const outbreak = feature.properties || {};
  // GeoJSON puts the position in geometry.coordinates as [lon, lat] — it is not
  // a `centroid` key on properties. Reading it from properties left this
  // undefined on every cluster, so the card always showed the hardcoded
  // "Nashik Cell" no matter where the outbreak actually was.
  const coords = feature.geometry?.coordinates;
  const position = Array.isArray(coords) && coords.length === 2
    ? `${coords[1].toFixed(4)}, ${coords[0].toFixed(4)}`
    : 'unavailable';

  const firstSeen = outbreak.first_seen
    ? new Date(outbreak.first_seen).toLocaleDateString()
    : null;

  return (
    <div style={{
      background: 'linear-gradient(135deg, #ff758c 0%, #ff7eb3 100%)',
      color: 'white',
      borderRadius: '16px',
      padding: '20px',
      boxShadow: '0 8px 24px rgba(255, 117, 140, 0.3)',
      marginTop: '20px'
    }}>
      <h3 style={{ margin: '0 0 8px 0', fontSize: '1.2rem' }}>
        🚨 Pre-emptive Outbreak Warning ({outbreak.alert_ring_km || 15} km Ring)
      </h3>
      <p style={{ margin: '0 0 12px 0', fontSize: '0.95rem' }}>
        An active <strong>{outbreak.disease || 'crop disease'}</strong> cluster (k ≥ 5) has been detected nearby.
      </p>
      <div style={{
        background: 'rgba(255, 255, 255, 0.2)',
        padding: '10px',
        borderRadius: '8px',
        fontSize: '0.85rem',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <span>📍 Centroid: {position}</span>
        {outbreak.radius_km !== undefined && <span>📏 Cluster extent: {outbreak.radius_km} km</span>}
        {firstSeen && <span>🕒 First seen: {firstSeen}</span>}
      </div>
    </div>
  );
}
