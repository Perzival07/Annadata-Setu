import React, { useEffect, useState } from 'react';
import AlertRing from '../components/AlertRing';
import { fetchOutbreaks } from '../api';

export default function OutbreakMapPage() {
  const [outbreaks, setOutbreaks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOutbreaks()
      .then((data) => {
        if (data && data.features) {
          setOutbreaks(data.features);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.85)',
      backdropFilter: 'blur(10px)',
      borderRadius: '16px',
      padding: '24px',
      boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15)'
    }}>
      <h2 style={{ margin: '0 0 16px 0', color: '#1b4332' }}>
        🗺️ Epidemiological Outbreak Heatmap (k ≥ 5)
      </h2>
      <p style={{ color: '#555', fontSize: '0.95rem' }}>
        Real-time DBSCAN spatial clustering over 7-day disease telemetry. Clusters with less than 5 reports are masked for k-anonymity privacy.
      </p>

      {loading ? (
        <p style={{ color: '#888' }}>Loading active disease clusters...</p>
      ) : outbreaks.length === 0 ? (
        <p style={{ color: '#2e7d32' }}>No active disease clusters detected above k ≥ 5 threshold.</p>
      ) : (
        <div>
          {outbreaks.map((feature, idx) => (
            <AlertRing key={idx} outbreak={feature.properties} />
          ))}
        </div>
      )}
    </div>
  );
}
