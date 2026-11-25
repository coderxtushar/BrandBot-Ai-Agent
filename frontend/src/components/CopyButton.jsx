import { useState } from 'react';
import { Check, Copy } from 'lucide-react';

export default function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked */ }
  };
  return (
    <button type="button" onClick={copy} className="btn-ghost px-3 py-1.5 text-xs">
      {copied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
      {copied ? 'Copied' : label}
    </button>
  );
}
