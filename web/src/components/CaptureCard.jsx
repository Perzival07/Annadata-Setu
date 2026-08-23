import React, { useState } from 'react';
import { LANGUAGE_NAMES, languageForState } from '../locations';
import { fetchPlace } from '../api';

// Nashik — where the demo is set. Only a starting value for the manual boxes;
// it is never submitted as if it were the farmer's captured position.
const FALLBACK_LAT = 19.9975;
const FALLBACK_LON = 73.7898;

export default function CaptureCard({ onDiagnose, loading }) {
  const [lat, setLat] = useState(FALLBACK_LAT);
  const [lon, setLon] = useState(FALLBACK_LON);
  const [captured, setCaptured] = useState(false);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState(null);
  const [place, setPlace] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [validationError, setValidationError] = useState(null);

  // Resolve a coordinate to its district so the farmer sees where they were
  // placed, and which language they will be answered in, before committing.
  const resolvePlace = async (nextLat, nextLon) => {
    setPlace(null);
    try {
      const found = await fetchPlace(nextLat, nextLon);
      setPlace(found && found.resolved ? found : { resolved: false });
    } catch {
      // A failed lookup is not a failed capture — the coordinates are still
      // good and the backend resolves them again anyway. Say nothing rather
      // than showing a district we did not actually get.
      setPlace({ resolved: false });
    }
  };

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('This browser cannot share a location. Enter coordinates below instead.');
      return;
    }
    setLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const nextLat = parseFloat(pos.coords.latitude.toFixed(4));
        const nextLon = parseFloat(pos.coords.longitude.toFixed(4));
        setLat(nextLat);
        setLon(nextLon);
        setCaptured(true);
        setLocating(false);
        resolvePlace(nextLat, nextLon);
      },
      (err) => {
        setLocating(false);
        // Distinguish the causes: "denied" is a decision the farmer made and
        // can undo, the others are conditions they cannot act on.
        const reason =
          err.code === err.PERMISSION_DENIED
            ? 'Location permission was denied. Allow it, or enter coordinates below.'
            : err.code === err.POSITION_UNAVAILABLE
            ? 'Your position could not be determined. Enter coordinates below.'
            : 'Locating timed out. Try again, or enter coordinates below.';
        setLocationError(reason);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  const handleManual = (setter) => (e) => {
    const value = parseFloat(e.target.value);
    setter(Number.isNaN(value) ? 0 : value);
    setCaptured(false);
    setPlace(null);
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

  const language = place && place.resolved ? languageForState(place.state) : null;

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
        📸 Upload Leaf Photo & Location
      </h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', color: '#2d6a4f' }}>
            Location:
          </label>
          <button
            type="button"
            onClick={handleUseMyLocation}
            disabled={locating}
            style={{
              width: '100%', padding: '12px', borderRadius: '12px',
              border: '1px solid #2d6a4f', background: captured ? '#d8f3dc' : 'white',
              color: '#1b4332', fontWeight: 'bold', fontSize: '0.95rem',
              cursor: locating ? 'wait' : 'pointer'
            }}
          >
            {locating ? '📍 Locating…' : captured ? '📍 Location captured — tap to update' : '📍 Use my current location'}
          </button>

          {captured && (
            <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: '#2d6a4f' }}>
              Captured: {lat}, {lon}
            </p>
          )}

          {place && place.resolved && (
            <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#2d6a4f' }}>
              📌 {place.district}, {place.state} — 🗣️ voice note in <strong>{LANGUAGE_NAMES[language]}</strong>
            </p>
          )}
          {place && !place.resolved && (
            <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#8a6d1f' }}>
              Could not name this district. The diagnosis still works — the language
              will follow whichever state the pin resolves to.
            </p>
          )}

          {locationError && (
            <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: '#a8071a' }}>
              {locationError}
            </p>
          )}

          <details style={{ marginTop: '10px' }}>
            <summary style={{ cursor: 'pointer', fontSize: '0.85rem', color: '#555' }}>
              Enter coordinates manually
            </summary>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '10px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#555' }}>Latitude:</label>
                <input
                  type="number" step="any" value={lat} onChange={handleManual(setLat)}
                  style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid #ccc' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#555' }}>Longitude:</label>
                <input
                  type="number" step="any" value={lon} onChange={handleManual(setLon)}
                  style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid #ccc' }}
                />
              </div>
            </div>
            <button
              type="button"
              onClick={() => resolvePlace(lat, lon)}
              style={{
                marginTop: '8px', padding: '8px 12px', borderRadius: '8px',
                border: '1px solid #ccc', background: 'white', cursor: 'pointer', fontSize: '0.85rem'
              }}
            >
              Check this location
            </button>
          </details>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', color: '#2d6a4f' }}>
            Leaf Image:
          </label>
          <input
            type="file"
            accept="image/*"
            capture="environment"
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
