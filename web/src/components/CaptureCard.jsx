import React, { useState } from 'react';
import { LOCATIONS, LANGUAGE_NAMES, languageForState } from '../locations';

export default function CaptureCard({ onDiagnose, loading }) {
  const [selected, setSelected] = useState(0);
  const [custom, setCustom] = useState(false);
  const [lat, setLat] = useState(LOCATIONS[0].lat);
  const [lon, setLon] = useState(LOCATIONS[0].lon);
  const [imagePreview, setImagePreview] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Shown so the demo is legible before the reply arrives. For a preset this is
  // the verified state; for custom coordinates the state is not known until the
  // backend geocodes the pin, so we say so rather than guessing.
  const place = custom ? null : LOCATIONS[selected];
  const expected = place ? LANGUAGE_NAMES[languageForState(place.state)] : null;

  const handleLocationChange = (e) => {
    const value = e.target.value;
    if (value === 'custom') {
      setCustom(true);
      return;
    }
    const index = parseInt(value, 10);
    setCustom(false);
    setSelected(index);
    setLat(LOCATIONS[index].lat);
    setLon(LOCATIONS[index].lon);
  };

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
    // No placeholder URL: without a real photo there is nothing to diagnose,
    // and a stand-in only produces a confident answer about someone else's leaf.
    if (!imagePreview) {
      setValidationError('Please attach a photo of the affected leaf first.');
      return;
    }
    setValidationError(null);
    onDiagnose({ imageUrl: imagePreview, lat, lon });
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
            Location:
          </label>
          <select
            value={custom ? 'custom' : selected}
            onChange={handleLocationChange}
            style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #ccc', background: 'white' }}
          >
            {[...new Set(LOCATIONS.map((l) => l.state))].map((state) => (
              <optgroup key={state} label={state}>
                {LOCATIONS.map((l, i) =>
                  l.state === state ? (
                    <option key={`${l.district}-${i}`} value={i}>
                      {l.district} — {LANGUAGE_NAMES[languageForState(l.state)]}
                    </option>
                  ) : null
                )}
              </optgroup>
            ))}
            <option value="custom">Custom coordinates…</option>
          </select>
          {expected && (
            <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: '#2d6a4f' }}>
              🗣️ Voice note will be in <strong>{expected}</strong>.
            </p>
          )}
          {custom && (
            <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: '#777' }}>
              🗣️ Language follows whichever state the pin falls in — West Bengal is
              answered in Bengali, Maharashtra in Marathi, everywhere else in Hindi.
            </p>
          )}
        </div>

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

        <div style={{
          display: custom ? 'grid' : 'none',
          gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px'
        }}>
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

        {validationError && (
          <div style={{
            background: '#fff1f0', color: '#a8071a', border: '1px solid #ffa39e',
            padding: '10px 12px', borderRadius: '8px', marginBottom: '12px', fontSize: '0.9rem'
          }}>
            {validationError}
          </div>
        )}

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
