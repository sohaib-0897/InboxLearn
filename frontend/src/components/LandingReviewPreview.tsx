import { useRef, useState } from 'react';
import { motion } from 'motion/react';
import { useMotionPreference } from '../useMotionPreference';
import { ArrowLeft } from 'lucide-react';

// Deliberately local fixtures: this component never imports the API client.
const examples = [
  { subject: 'A receipt, or a renewal?', sender: 'Mara at Papertrail', category: 'bills', priority: 'normal', confidence: '61%', body: 'Your studio subscription renews on Friday. Please confirm the new billing contact before we send the invoice.' },
  { subject: 'Study group next week', sender: 'Sam Rivera', category: 'university', priority: 'low', confidence: '88%', body: 'Would Tuesday work for our study group? I found a quiet place near campus. No rush — let me know when you can.' },
  { subject: 'Delivery needs your attention', sender: 'Studio Supplies', category: 'promotions', priority: 'normal', confidence: '54%', body: 'We could not deliver your order today. Please confirm the delivery address by tomorrow so we can try again.' },
];
type Labels = { category: string; priority: string };

export function LandingReviewPreview() {
  const [selected, setSelected] = useState(0);
  const [drafts, setDrafts] = useState<Record<number, Labels>>({});
  const [confirmed, setConfirmed] = useState<Record<number, Labels>>({});
  const [notice, setNotice] = useState('Choose a message, then try confirming or changing its labels.');
  const listRef = useRef<HTMLButtonElement>(null);
  const detailRef = useRef<HTMLHeadingElement>(null);
  const reduced = useMotionPreference();
  const message = examples[selected];
  const draft = drafts[selected] ?? confirmed[selected] ?? message;

  const selectMessage = (index: number) => {
    setSelected(index);
    setNotice('Selected synthetic message. Its original suggestion stays visible.');
    // On narrow screens the pane follows the list; move focus to the reading context.
    if (window.matchMedia('(max-width: 760px)').matches) detailRef.current?.focus();
  };
  const updateDraft = (field: keyof Labels, value: string) => {
    setDrafts((previous) => ({ ...previous, [selected]: { ...draft, [field]: value } }));
    setNotice('Label change pending. Apply it to this preview when ready.');
  };

  return (
    <div className="landing-preview">
      <div className="preview-masthead">
        <div><span className="preview-eyebrow">TRY THE REVIEW DESK</span><p>Preview only; nothing saved or trained.</p></div>
        <button type="button" className="preview-reset" onClick={() => {
          setSelected(0); setDrafts({}); setConfirmed({});
          setNotice('Preview reset. All simulated confirmations and label changes cleared.');
        }}>Reset preview</button>
      </div>
      <div className="preview-columns">
        <div className="preview-queue" aria-label="Synthetic messages">
          <p className="preview-eyebrow">THREE MESSAGES. YOUR CALL.</p>
          {examples.map((example, index) => (
            <button key={example.subject} type="button" ref={index === selected ? listRef : undefined}
              aria-pressed={selected === index} aria-controls="preview-reading-pane"
              className={`preview-message ${selected === index ? 'is-selected' : ''}`}
              onClick={() => selectMessage(index)}>
              <span>{example.sender}</span><strong>{example.subject}</strong>
              <small>{confirmed[index] ? 'Human-confirmed in preview' : `Model suggestion · ${example.confidence} category confidence`}</small>
            </button>
          ))}
        </div>
        <div id="preview-reading-pane" className="preview-reading">
          <button type="button" className="preview-return" onClick={() => listRef.current?.focus()}><ArrowLeft size={15} aria-hidden="true" /> Back to messages</button>
          <p className="preview-eyebrow">SYNTHETIC EMAIL / FROM {message.sender}</p>
          <h3 ref={detailRef} tabIndex={-1}>{message.subject}</h3>
          <p className="preview-email-body">{message.body}</p>
          <dl className="preview-suggestion"><dt>Original model suggestion</dt><dd>{message.category} / {message.priority}</dd><dt>Illustrative category confidence</dt><dd>{message.confidence}</dd></dl>
          <form onSubmit={(event) => {
            event.preventDefault();
            setConfirmed((previous) => ({ ...previous, [selected]: { category: draft.category, priority: draft.priority } }));
            setNotice(`Simulated confirmation: ${draft.category} / ${draft.priority}. Nothing saved or trained.`);
          }}>
            <div className="preview-fields">
              <label htmlFor="preview-category">Your category<select id="preview-category" value={draft.category} onChange={(event) => updateDraft('category', event.target.value)}>
                {['job opportunities', 'university', 'bills', 'promotions', 'spam'].map((value) => <option key={value}>{value}</option>)}
              </select></label>
              <label htmlFor="preview-priority">Your priority<select id="preview-priority" value={draft.priority} onChange={(event) => updateDraft('priority', event.target.value)}>
                {['low', 'normal', 'high'].map((value) => <option key={value}>{value}</option>)}
              </select></label>
            </div>
            {confirmed[selected] && <p className="preview-confirmed"><strong>Human-confirmed in preview:</strong> {confirmed[selected].category} / {confirmed[selected].priority}</p>}
            <button type="submit" className="preview-apply">Apply to preview</button>
          </form>
        </div>
      </div>
      <p className="preview-notice" role="status" aria-live="polite">
        <motion.span key={notice} initial={{ opacity: reduced ? 1 : .65 }} animate={{ opacity: 1 }} transition={{ duration: reduced ? 0 : .18 }}>{notice}</motion.span>
      </p>
    </div>
  );
}
