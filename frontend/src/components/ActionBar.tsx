import { useState } from 'react';
import { Check, Copy, ExternalLink, Mail, MailPlus, MapPin, Phone } from 'lucide-react';
import type { SeraAction } from '../api/types';

const ICONS = {
  email_draft: MailPlus,
  email: Mail,
  call: Phone,
  map: MapPin,
  link: ExternalLink,
  copy: Copy,
} as const;

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Clipboard API needs https or localhost; fall back for http://<LAN-IP> (phones on the same Wi-Fi).
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

/** Proactive buttons under a Sera reply. They only open the student's own apps; nothing is sent automatically. */
export function ActionBar({ actions }: { actions?: SeraAction[] }) {
  const [copied, setCopied] = useState<number | null>(null);
  if (!actions?.length) return null;

  return (
    <div className="action-bar" aria-label="Suggested actions">
      {actions.map((action, i) => {
        const Icon = action.type === 'copy' && copied === i ? Check : ICONS[action.type];
        if (action.type === 'copy') {
          return (
            <button key={i} type="button" className="action-chip"
              onClick={async () => { if (action.text && await copyText(action.text)) { setCopied(i); setTimeout(() => setCopied(null), 1800); } }}>
              <Icon size={13} /> {copied === i ? 'Copied' : action.label}
            </button>
          );
        }
        const external = action.type === 'link' || action.type === 'map';
        return (
          <a key={i} className={`action-chip action-${action.type}`} href={action.href ?? undefined}
            {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}>
            <Icon size={13} /> {action.label}
          </a>
        );
      })}
    </div>
  );
}
