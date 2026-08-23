import React from 'react';

export default function DashboardPage() {
  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.85)',
      backdropFilter: 'blur(10px)',
      borderRadius: '16px',
      padding: '24px',
      boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15)'
    }}>
      <h2 style={{ margin: '0 0 16px 0', color: '#1b4332' }}>
        📊 District Agriculture Officer Dashboard
      </h2>
      <p style={{ color: '#555', fontSize: '0.95rem' }}>
        BigQuery → Looker Studio real-time executive surveillance dashboard.
      </p>

      <div style={{
        height: '450px',
        background: '#e9ecef',
        borderRadius: '12px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#6c757d',
        border: '2px dashed #adb5bd'
      }}>
        <h3 style={{ margin: '0 0 8px 0' }}>📈 Looker Studio Embedded Analytics</h3>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>
          District Officer Surveillance View: Disease Frequency, Cost Savings, and Chemical Reduction Metrics.
        </p>
      </div>
    </div>
  );
}
