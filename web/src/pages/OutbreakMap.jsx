import React, { useEffect, useState } from 'react';
import AlertRing from '../components/AlertRing';
import { fetchOutbreaks } from '../api';

export default function OutbreakMapPage() {
  const [outbreaks, setOutbreaks] = useState([]);
  const [loading, setLoading] = useState(true);
  // A failed fetch and a genuinely quiet district are different facts. Showing
  // "no active clusters" when the request actually errored tells a district
  // officer the all-clear on evidence we never received.
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchOutbreaks()
      .then((data) => setOutbreaks(data?.features ?? []))
      .catch((err) => {
        console.error(err);
        setError('Could not reach the outbreak service — this is not an all-clear.');
      })
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
        Real-time DBSCAN spatial clustering over 7-day disease telemetry. Clusters with fewer than 5 reports are masked for k-anonymity.
      </p>

      {loading && <p style={{ color: '#888' }}>Loading active disease clusters...</p>}

      {!loading && error && (
        <div style={{
          background: '#fff1f0', color: '#a8071a', border: '1px solid #ffa39e',
          padding: '12px', borderRadius: '8px'
        }}>
          ⚠️ {error}
        </div>
      )}

      {!loading && !error && outbreaks.length === 0 && (
        <p style={{ color: '#2e7d32' }}>
          No active disease clusters above the k ≥ 5 threshold in the last 7 days.
        </p>
      )}

      {!loading && !error && outbreaks.map((feature, idx) => (
        <AlertRing key={feature.properties?.cluster_id ?? idx} feature={feature} />
      ))}
    </div>
  );
}
