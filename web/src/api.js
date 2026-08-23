// Centralized API configuration for Annadata Setu

export const CHANNEL_URL = import.meta.env.VITE_CHANNEL_URL || 'http://localhost:8001';
export const BRAIN_URL = import.meta.env.VITE_BRAIN_URL || 'http://localhost:8002';
export const GROUND_URL = import.meta.env.VITE_GROUND_URL || 'http://localhost:8003';

export async function fetchDiagnosis(image, lat, lon) {
  // A `data:` URI is not something the brain service can fetch over HTTP — it
  // has to travel as raw base64 in image_base64, or the photo never reaches
  // Gemini and the diagnosis is made from plot context alone.
  const body = { lat, lon };
  if (typeof image === 'string' && image.startsWith('data:')) {
    body.image_base64 = image.split(',')[1];
  } else if (image) {
    body.image_url = image;
  }

  const res = await fetch(`${CHANNEL_URL}/api/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error('Diagnosis request failed');
  return await res.json();
}

export async function fetchOutbreaks() {
  const res = await fetch(`${BRAIN_URL}/api/v1/outbreaks`);
  if (!res.ok) throw new Error('Outbreaks fetch failed');
  return await res.json();
}
