import React, { useState } from 'react';

export default function CaptureCard({ onDiagnose, loading }) {
  const [lat, setLat] = useState(19.9975);
  const [lon, setLon] = useState(73.7898);
  const [imagePreview, setImagePreview] = useState(null);

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result);
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onDiagnose({ imageUrl: imagePreview || 'http://mock.url/leaf.jpg', lat, lon });
  };

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.85)',
      backdropFilter: 'blur(10px)',
      borderRadius: '16px',
      padding: '24px',
      boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
      border: '1px solid rgba(255, 255, 255, 0.18)',
      marginBottom: '20px'
    }}>
      <h2 style={{ margin: '0 0 16px 0', color: '#1b4332', fontSize: '1.25rem' }}>
        📸 Upload Leaf Photo & Location Pin
      </h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', color: '#2d6a4f' }}>
            Leaf Image:
          </label>
          <input
            type="file"
            accept="image/*"
            onChange={handleImageChange}
            style={{ width: '100%', padding: '8px' }}
          />
          {imagePreview && (
            <img
              src={imagePreview}
              alt="Leaf Preview"
              style={{ marginTop: '12px', maxHeight: '180px', borderRadius: '12px' }}
            />
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#555' }}>Latitude:</label>
            <input
              type="number"
              step="any"
              value={lat}
              onChange={(e) => setLat(parseFloat(e.target.value))}
              style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid #ccc' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#555' }}>Longitude:</label>
            <input
              type="number"
              step="any"
              value={lon}
              onChange={(e) => setLon(parseFloat(e.target.value))}
              style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid #ccc' }}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            width: '100%',
            padding: '12px',
            backgroundColor: '#2d6a4f',
            color: 'white',
            border: 'none',
            borderRadius: '12px',
            fontSize: '1rem',
            fontWeight: 'bold',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'background 0.3s ease'
          }}
        >
          {loading ? 'Analyzing Plot Telemetry & Gemini...' : '🌱 Diagnose My Crop'}
        </button>
      </form>
    </div>
  );
}
