import React, { useState } from 'react';
import FarmerPage from './pages/Farmer';
import OutbreakMapPage from './pages/OutbreakMap';
import DashboardPage from './pages/Dashboard';

export default function App() {
  const [activeTab, setActiveTab] = useState('farmer');

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#f4f6f8',
      backgroundImage: 'radial-gradient(#2d6a4f 0.5px, transparent 0.5px), radial-gradient(#2d6a4f 0.5px, #f4f6f8 0.5px)',
      backgroundSize: '20px 20px',
      backgroundPosition: '0 0, 10px 10px',
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      color: '#2b2d42'
    }}>
      {/* Header Bar */}
      <header style={{
        background: 'rgba(27, 67, 50, 0.95)',
        backdropFilter: 'blur(10px)',
        color: 'white',
        padding: '16px 32px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.8rem' }}>🌾</span>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 'bold' }}>Annadata Setu</h1>
            <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>🌱 अन्नदाता सेतु | WhatsApp-Native Agricultural Nervous System</span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'farmer', label: '👨‍🌾 Farmer PWA' },
            { id: 'map', label: '🗺️ Outbreak Map' },
            { id: 'dashboard', label: '📊 Officer Dashboard' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '8px 16px',
                borderRadius: '20px',
                border: 'none',
                backgroundColor: activeTab === tab.id ? '#52b788' : 'transparent',
                color: activeTab === tab.id ? '#1b4332' : 'white',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Main Content View */}
      <main style={{ padding: '32px 16px', maxWidth: '1000px', margin: '0 auto' }}>
        {activeTab === 'farmer' && <FarmerPage />}
        {activeTab === 'map' && <OutbreakMapPage />}
        {activeTab === 'dashboard' && <DashboardPage />}
      </main>
    </div>
  );
}
