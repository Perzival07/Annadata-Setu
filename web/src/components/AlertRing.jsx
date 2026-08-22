import React from 'react';

export default function AlertRing({ outbreak }) {
  if (!outbreak) return null;

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
        🚨 Pre-emptive Outbreak Warning (15km Ring)
      </h3>
      <p style={{ margin: '0 0 12px 0', fontSize: '0.95rem' }}>
        An active <strong>{outbreak.disease}</strong> cluster ($k \ge 5$) has been detected nearby!
      </p>
      <div style={{ background: 'rgba(255, 255, 255, 0.2)', padding: '10px', borderRadius: '8px', fontSize: '0.85rem' }}>
        <span>📍 Centroid: {outbreak.centroid ? outbreak.centroid.join(', ') : 'Nashik Cell'}</span>
        <span style={{ marginLeft: '16px' }}>🛡️ Alert Zone: {outbreak.alert_ring_km || 15} km</span>
      </div>
    </div>
  );
}
