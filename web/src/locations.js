// Language naming, and the state → language rule mirrored from the backend.
//
// The authority is channel/services/languages.py. This copy exists only so the
// page can tell the farmer which language they will be answered in before they
// submit; if the two ever disagree, the backend is right and this file is stale.
//
// The rule: West Bengal → Bengali, Maharashtra → Marathi, everywhere else → Hindi.

export const LANGUAGE_NAMES = {
  mr: 'Marathi',
  hi: 'Hindi',
  bn: 'Bengali',
  en: 'English',
};

export function languageForState(state) {
  if (state === 'West Bengal') return 'bn';
  if (state === 'Maharashtra') return 'mr';
  return 'hi';
}
