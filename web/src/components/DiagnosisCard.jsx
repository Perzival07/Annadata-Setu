import React from 'react';

export default function DiagnosisCard({ data }) {
  if (!data) return null;
  const { diagnosis, passport, formatted_text, voice_script, marathi_script, language } = data;
  // voice_script is the current field; marathi_script is its deprecated alias.
  const spokenScript = voice_script || marathi_script;
  const LANGUAGE_NAMES = { mr: 'Marathi', hi: 'Hindi', bn: 'Bengali', en: 'English' };
  const spokenLanguage = LANGUAGE_NAMES[language] || 'Marathi';

  // Escalation is a third state, resolved before anything else. It is neither
  // "spray this" nor "you're fine" — rendering it through is_action_needed
  // would show a green "Don't Spray — Save Money" badge to a farmer whose leaf
  // was never actually examined. Mirrors channel/services/composer.py.
  const isEscalated = diagnosis.escalate_to_human;
  const isActionNeeded = diagnosis.is_action_needed;

  const badge = isEscalated
    ? { text: 'Under Review — Do Not Spray', color: '#d46b08' }
    : isActionNeeded
      ? { text: 'Action Needed', color: '#ff4d4f' }
      : { text: "Don't Spray — Save Money", color: '#52c41a' };

  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.9)',
      backdropFilter: 'blur(12px)',
      borderRadius: '16px',
      padding: '24px',
      boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
      border: '1px solid rgba(255, 255, 255, 0.18)',
      marginTop: '20px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h3 style={{ margin: 0, color: '#1b4332', fontSize: '1.3rem' }}>
          {isEscalated ? '🔬' : '🩺'} {isEscalated ? 'Undetermined — sent for expert review' : diagnosis.disease_name}
        </h3>
        <span style={{
          backgroundColor: badge.color,
          color: 'white',
          padding: '4px 12px',
          borderRadius: '20px',
          fontWeight: 'bold',
          fontSize: '0.85rem'
        }}>
          {badge.text}
        </span>
      </div>

      <div style={{ background: '#f8f9fa', padding: '12px', borderRadius: '10px', marginBottom: '16px' }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: '#333' }}>
          <strong>Plot Context:</strong> {passport.district}, {passport.state} ({passport.inferred_crop} Day {passport.crop_stage_days})
        </p>
        {passport.soil?.ph !== undefined && passport.weather_10d?.rh_avg !== undefined ? (
          <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#666' }}>
            Soil pH: {passport.soil.ph} | SOC: {passport.soil.soc} | 10d RH Avg: {passport.weather_10d.rh_avg}%
          </p>
        ) : (
          <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#999' }}>
            Plot telemetry unavailable for this request.
          </p>
        )}
      </div>

      <div style={{ marginBottom: '16px' }}>
        <h4 style={{ margin: '0 0 8px 0', color: '#2d6a4f' }}>🔍 Reasoning Context:</h4>
        <ul style={{ margin: 0, paddingLeft: '20px', color: '#444', fontSize: '0.9rem' }}>
          {diagnosis.reasoning_context.map((note, idx) => (
            <li key={idx}>{note}</li>
          ))}
        </ul>
      </div>

      <div style={{
        backgroundColor: '#e8f5e9',
        borderLeft: '4px solid #2d6a4f',
        padding: '12px',
        borderRadius: '4px',
        marginBottom: '16px'
      }}>
        <h4 style={{ margin: '0 0 4px 0', color: '#1b4332' }}>🌱 Actionable Advice:</h4>
        <p style={{ margin: 0, color: '#2e7d32', fontWeight: '500' }}>{diagnosis.action_text}</p>
        {!isEscalated && isActionNeeded && (
          <p style={{ margin: '6px 0 0 0', fontSize: '0.85rem', color: '#1b5e20' }}>
            <strong>Dosage:</strong> {diagnosis.dosage} | <strong>Est. Cost:</strong> ₹{diagnosis.estimated_cost_inr}
          </p>
        )}
      </div>

      {spokenScript && (
        <div style={{ background: '#fff3e0', padding: '12px', borderRadius: '10px' }}>
          <h4 style={{ margin: '0 0 6px 0', color: '#e65100' }}>🗣️ Spoken Audio Advisory ({spokenLanguage}):</h4>
          <p style={{ margin: 0, fontStyle: 'italic', color: '#bf360c', fontSize: '0.95rem' }}>
            "{spokenScript}"
          </p>
        </div>
      )}
    </div>
  );
}
