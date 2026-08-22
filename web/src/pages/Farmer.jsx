import React, { useState } from 'react';
import CaptureCard from '../components/CaptureCard';
import DiagnosisCard from '../components/DiagnosisCard';
import { fetchDiagnosis } from '../api';

export default function FarmerPage() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleDiagnose = async ({ imageUrl, lat, lon }) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDiagnosis(imageUrl, lat, lon);
      setResult(data);
    } catch (err) {
      setError('Diagnosis failed. Please check backend service connectivity.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <CaptureCard onDiagnose={handleDiagnose} loading={loading} />
      {error && (
        <div style={{ color: 'red', background: '#ffe6e6', padding: '12px', borderRadius: '8px', marginTop: '12px' }}>
          {error}
        </div>
      )}
      <DiagnosisCard data={result} />
    </div>
  );
}
