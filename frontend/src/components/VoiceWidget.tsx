import { createElement, useEffect } from 'react';

const AGENT_ID = (import.meta.env.VITE_ELEVENLABS_AGENT_ID as string | undefined)?.trim();
const SCRIPT_SRC = 'https://unpkg.com/@elevenlabs/convai-widget-embed';

/**
 * ElevenLabs voice agent (Person 2's agent, created in the ElevenLabs dashboard).
 * Shows as a floating call button in the bottom-right corner on every page.
 * Hidden unless VITE_ELEVENLABS_AGENT_ID is set in frontend/.env.
 * In the agent's Security tab, add this site's host (e.g. localhost:5173) to the allowlist.
 */
export function VoiceWidget() {
  useEffect(() => {
    if (!AGENT_ID || document.querySelector(`script[src="${SCRIPT_SRC}"]`)) return;
    const script = document.createElement('script');
    script.src = SCRIPT_SRC;
    script.async = true;
    script.type = 'text/javascript';
    document.body.appendChild(script);
  }, []);

  if (!AGENT_ID) return null;
  return createElement('elevenlabs-convai', { 'agent-id': AGENT_ID });
}
