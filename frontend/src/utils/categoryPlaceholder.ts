/**
 * Category icon helper for article image placeholders.
 */

export const getCategoryIcon = (category: string): string => {
  const cat = (category || '').toLowerCase();
  if (cat.includes('awari')) return '⚠️';
  if (cat === 'transport' || cat.startsWith('transport')) return '🚗';
  if (cat.includes('urząd') || cat.includes('urzad')) return '🏛️';
  if (cat.includes('kultur')) return '🎭';
  if (cat.includes('sport')) return '⚽';
  if (cat.includes('rekr')) return '🌿';
  if (cat.includes('edukac')) return '📚';
  if (cat.includes('zdrow')) return '🏥';
  if (cat.includes('biznes')) return '💼';
  if (cat.includes('nieruch')) return '🏠';
  if (cat.includes('polity')) return '🗳️';
  return '📰';
};
