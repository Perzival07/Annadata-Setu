// Preset farming locations for the picker.
//
// Every coordinate here was verified against the live reverse geocoder, so the
// district and state shown are what the backend will actually resolve — not a
// label typed alongside a guess. `language` is likewise not sent to the server:
// the backend derives it from the resolved state, and this field only tells the
// person choosing what to expect. If the two ever disagree, the backend is
// right and this file is stale.
//
// The rule the backend applies:
//   West Bengal -> Bengali, Maharashtra -> Marathi, everywhere else -> Hindi.

export const LANGUAGE_NAMES = {
  mr: 'Marathi',
  hi: 'Hindi',
  bn: 'Bengali',
  en: 'English',
};

export const LOCATIONS = [
  { state: 'Maharashtra', district: 'Nashik', lat: 19.9975, lon: 73.7898, language: 'mr' },
  { state: 'Maharashtra', district: 'Nagpur', lat: 21.1458, lon: 79.0882, language: 'mr' },
  { state: 'West Bengal', district: 'North 24 Parganas', lat: 22.5726, lon: 88.3639, language: 'bn' },
  { state: 'West Bengal', district: 'Bankura', lat: 23.2324, lon: 87.069, language: 'bn' },
  { state: 'Uttar Pradesh', district: 'Lucknow', lat: 26.8467, lon: 80.9462, language: 'hi' },
  { state: 'Punjab', district: 'Ludhiana', lat: 30.901, lon: 75.8573, language: 'hi' },
  { state: 'Telangana', district: 'Hyderabad', lat: 17.385, lon: 78.4867, language: 'hi' },
];

/** What the backend will answer in for a given state. Mirrors channel/services/languages.py. */
export function languageForState(state) {
  if (state === 'West Bengal') return 'bn';
  if (state === 'Maharashtra') return 'mr';
  return 'hi';
}
