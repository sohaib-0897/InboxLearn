import { useSyncExternalStore } from 'react';

const query = '(prefers-reduced-motion: reduce)';
const getSnapshot = () => window.matchMedia(query).matches;
const getServerSnapshot = () => true;
function subscribe(onChange: () => void) {
  const preference = window.matchMedia(query);
  preference.addEventListener('change', onChange);
  return () => preference.removeEventListener('change', onChange);
}

/** Keep short UI transitions in sync with live OS/browser preference changes. */
export function useMotionPreference() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
