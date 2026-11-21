import { useId } from 'react';

/** Sera app mark: rounded square, violet gradient, lowercase "s" with a small spark. Vector, crisp at any size. */
export function SeraMark({ size = 38 }: { size?: number }) {
  const id = useId().replace(/:/g, '');
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Sera" className="sera-mark">
      <defs>
        <linearGradient id={`g${id}`} x1="8" y1="4" x2="58" y2="62" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#9A7BFF" />
          <stop offset="0.55" stopColor="#7332E9" />
          <stop offset="1" stopColor="#5A22C8" />
        </linearGradient>
        <linearGradient id={`h${id}`} x1="0" y1="0" x2="0" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#fff" stopOpacity=".28" />
          <stop offset=".5" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="18" fill={`url(#g${id})`} />
      <rect x="2" y="2" width="60" height="60" rx="18" fill={`url(#h${id})`} />
      <text x="30" y="45" textAnchor="middle" fill="#fff"
        style={{ font: "800 42px Manrope, 'Segoe UI', Arial, sans-serif", letterSpacing: '-1px' }}>s</text>
      <circle cx="47" cy="17" r="4.2" fill="#fff" />
    </svg>
  );
}

/** Full lockup for dark backgrounds: mark + "sera" wordmark (+ optional tagline). */
export function SeraLogo({ tagline }: { tagline?: string }) {
  return (
    <span className="sera-logo">
      <SeraMark size={38} />
      <span className="sera-logo-text">
        <span className="sera-wordmark">sera</span>
        {tagline && <small>{tagline}</small>}
      </span>
    </span>
  );
}
