import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, CalendarCheck, CheckCircle2, Clock, FlaskConical, Mail, Phone, PhoneCall, PhoneOff,
  RotateCcw, Settings2, ShieldCheck, Sparkles, Stethoscope, UserRound,
} from 'lucide-react';
import type { MissionLive, TriageResult } from '../api/types';
import { endpoints } from '../api/client';
import { Button, Field, Notice, Panel } from '../components/UI';
import { SpeakButton } from '../components/RichText';

const STAGE_MESSAGE = "I woke up sick with a high fever, I'm allergic to penicillin, and I can't attend my class today.";
const SETUP_KEY = 'sera-live-demo-setup';

interface Setup { doctorPhone: string; studentPhone: string; preferredWindow: string }

function loadSetup(): Setup {
  try {
    const saved = JSON.parse(localStorage.getItem(SETUP_KEY) || '{}');
    return { doctorPhone: saved.doctorPhone || '', studentPhone: saved.studentPhone || '', preferredWindow: saved.preferredWindow || 'Ma 15:00 előtt' };
  } catch {
    return { doctorPhone: '', studentPhone: '', preferredWindow: 'Ma 15:00 előtt' };
  }
}

const STEPS = [
  { key: 'triage', label: 'Triage', icon: UserRound },
  { key: 'permission', label: 'Permission', icon: ShieldCheck },
  { key: 'call', label: 'Calling doctor (HU)', icon: PhoneCall },
  { key: 'done', label: 'Appointment confirmed', icon: CalendarCheck },
] as const;

function stepIndex(status: MissionLive['status'] | undefined, triage: TriageResult | null): number {
  switch (status) {
    case 'COMPLETED': return 4;
    case 'SENDING_EMAIL': return 3;
    case 'CALLING_DOCTOR': case 'CALL_FAILED': return 2;
    case 'TRIAGE_DONE': return 1;
    default: return triage ? 1 : 0;
  }
}

const SOURCE_LABEL: Record<string, string> = {
  data_collection: 'confirmed by the agent',
  transcript: 'heard in the call',
  summary: 'from the call summary',
  fallback: 'not heard in the call: to be confirmed',
  manual: 'entered manually (fallback mode)',
};

export function LiveDemoPage() {
  const [setup, setSetup] = useState<Setup>(loadSetup);
  const [message, setMessage] = useState(STAGE_MESSAGE);
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [mission, setMission] = useState<MissionLive | null>(null);
  const [busy, setBusy] = useState<'' | 'triage' | 'call' | 'simulate' | 'reset'>('');
  const [error, setError] = useState('');
  const [declined, setDeclined] = useState(false);
  const [simTime, setSimTime] = useState('14:30');
  const [showSetup, setShowSetup] = useState(() => !loadSetup().doctorPhone);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    try { localStorage.setItem(SETUP_KEY, JSON.stringify(setup)); } catch { /* storage unavailable */ }
  }, [setup]);

  const refresh = useCallback(async () => {
    try { setMission(await endpoints.missionStatus()); } catch { /* keep last state */ }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Poll while a call is running
  useEffect(() => {
    const active = mission?.status === 'CALLING_DOCTOR' || mission?.status === 'SENDING_EMAIL';
    if (active && pollRef.current === null) {
      pollRef.current = window.setInterval(() => void refresh(), 1500);
    }
    if (!active && pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [mission?.status, refresh]);
  useEffect(() => () => { if (pollRef.current !== null) window.clearInterval(pollRef.current); }, []);

  async function runTriage() {
    setError(''); setDeclined(false); setBusy('triage');
    try {
      setTriage(await endpoints.triage(message));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Triage failed.');
    } finally { setBusy(''); }
  }

  async function confirmAndCall() {
    if (!triage) return;
    setError(''); setBusy('call');
    try {
      await endpoints.confirmAndExecute({
        doctor_phone: setup.doctorPhone,
        student_phone: setup.studentPhone || undefined,
        student_name: triage.student_name,
        course_name: triage.course_name,
        symptoms: triage.symptoms_hu,       // the agent speaks Hungarian to the doctor
        allergies: triage.allergies_hu,
        preferred_window: setup.preferredWindow,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The call could not be started.');
    } finally {
      setBusy('');
      await refresh();
    }
  }

  async function simulate() {
    setError(''); setBusy('simulate');
    try { setMission(await endpoints.simulateCallComplete(simTime.trim() || undefined)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Simulation failed.'); }
    finally { setBusy(''); }
  }

  async function reset() {
    setBusy('reset');
    try { setMission(await endpoints.missionReset()); } catch { /* ignore */ }
    setTriage(null); setDeclined(false); setError(''); setBusy('');
  }

  const status = mission?.status;
  const current = stepIndex(status, triage);
  const phoneValid = /^\+[1-9]\d{7,14}$/.test(setup.doctorPhone.replace(/[\s\-()]/g, ''));
  const calling = status === 'CALLING_DOCTOR';
  const done = status === 'COMPLETED';

  return (
    <div className="page-stack live-demo">
      <div className="page-heading-row">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> AUTONOMOUS CAMPUS CONCIERGE</div>
          <h1>Live demo</h1>
          <p className="page-lede">Sick student → Sera calls the campus doctor in Hungarian → appointment confirmed.</p>
        </div>
        <div className="assistant-controls">
          <Button variant="secondary" onClick={() => setShowSetup((v) => !v)}><Settings2 size={15} /> Setup</Button>
          <Button variant="secondary" onClick={() => void reset()} disabled={busy !== ''}><RotateCcw size={15} /> Reset</Button>
        </div>
      </div>

      {showSetup && <Panel title="Stage setup" subtitle="Saved on this device. Phone numbers in international format.">
        <div className="live-setup-grid">
          <Field label="Doctor phone (judge)"><input value={setup.doctorPhone} placeholder="+36 30 123 4567" inputMode="tel"
            onChange={(e) => setSetup({ ...setup, doctorPhone: e.target.value })} /></Field>
          <Field label="Student phone (optional)"><input value={setup.studentPhone} placeholder="+36 …" inputMode="tel"
            onChange={(e) => setSetup({ ...setup, studentPhone: e.target.value })} /></Field>
          <Field label="Preferred time window (Hungarian)"><input value={setup.preferredWindow}
            onChange={(e) => setSetup({ ...setup, preferredWindow: e.target.value })} /></Field>
        </div>
        {setup.doctorPhone && !phoneValid && <Notice tone="warning">Use international format, e.g. +36301234567.</Notice>}
      </Panel>}

      <ol className="live-steps">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const state = i < current ? 'done' : i === current ? 'active' : 'todo';
          return <li key={s.key} className={`live-step ${state} ${status === 'CALL_FAILED' && i === 2 ? 'failed' : ''}`}>
            <span className="live-step-icon">{state === 'done' ? <CheckCircle2 size={16} /> : <Icon size={16} />}</span>
            <span>{s.label}</span>
          </li>;
        })}
      </ol>

      {error && <Notice tone="danger">{error}</Notice>}

      <div className="live-grid">
        <section className="live-col">
          <Panel title="1. Student" subtitle="What the student says (English).">
            <div className="explain-form">
              <textarea rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
              <div className="inline-actions">
                <Button onClick={() => void runTriage()} disabled={busy !== '' || message.trim().length < 3 || calling}>
                  <Sparkles size={14} /> {busy === 'triage' ? 'Understanding…' : 'Send to Sera'}
                </Button>
              </div>
            </div>
          </Panel>

          {triage && <Panel title="2. Sera understood" subtitle="Extracted by the backend, no guessing.">
            <dl className="live-facts">
              <div><dt>Student</dt><dd>{triage.student_name}</dd></div>
              <div><dt>Course</dt><dd>{triage.course_name}</dd></div>
              <div><dt>Symptoms</dt><dd>{triage.symptoms} <span className="hu">· {triage.symptoms_hu}</span></dd></div>
              <div><dt>Allergies</dt><dd>{triage.allergies} <span className="hu">· {triage.allergies_hu}</span></dd></div>
            </dl>
            {triage.emergency
              ? <Notice tone="danger"><AlertTriangle size={15} /> {triage.confirmation_question}</Notice>
              : <div className="live-question">
                  <div className="live-question-text"><Sparkles size={15} /> {triage.confirmation_question}
                    <SpeakButton text={triage.confirmation_question} language="en" /></div>
                  {!done && !calling && !declined && <div className="inline-actions">
                    <Button onClick={() => void confirmAndCall()} disabled={busy !== '' || !phoneValid}>
                      <Phone size={14} /> {busy === 'call' ? 'Starting call…' : 'Yes, call the doctor'}
                    </Button>
                    <Button variant="ghost" onClick={() => setDeclined(true)} disabled={busy !== ''}>No</Button>
                  </div>}
                  {!phoneValid && !calling && !done && <span className="subtle-footnote">Add the doctor's phone in Setup first.</span>}
                  {declined && <Notice tone="info">OK, nothing was done. Sera only acts with the student's permission.</Notice>}
                </div>}
          </Panel>}
        </section>

        <section className="live-col">
          <Panel title="3. Live mission" subtitle="Updates automatically from the call.">
            <div className={`live-status live-status-${(status || 'IDLE').toLowerCase()}`}>
              {calling && <><span className="pulse-dot" /><div><strong>Calling the doctor in Hungarian…</strong><span>{mission?.contacts.doctor_phone}</span></div></>}
              {status === 'SENDING_EMAIL' && <><Clock size={20} /><div><strong>Call finished, wrapping up…</strong></div></>}
              {status === 'CALL_FAILED' && <><PhoneOff size={20} /><div><strong>The call could not be started</strong><span>Check the reason below, or use the fallback.</span></div></>}
              {done && <><CalendarCheck size={22} /><div>
                <strong>Appointment today at {mission?.appointment_time}</strong>
                <span>{SOURCE_LABEL[mission?.appointment_time_source || ''] || ''}</span>
              </div></>}
              {(!status || status === 'IDLE' || status === 'TRIAGE_DONE') && <><Stethoscope size={20} /><div><strong>Waiting for the student's permission</strong></div></>}
            </div>

            {done && mission && <div className="live-result">
              {mission.email.status === 'sent' && <div><Mail size={14} /> Absence email sent to <strong>{mission.email.to}</strong></div>}
              {mission.email.status === 'failed' && <div><Mail size={14} /> Absence email failed: {mission.email.error}</div>}
              {mission.transcript_excerpt && <details className="source-text"><summary>Call transcript (last lines)</summary><pre>{mission.transcript_excerpt}</pre></details>}
            </div>}

            {mission && mission.events.length > 0 && <ul className="live-timeline">
              {mission.events.slice().reverse().map((e, i) => <li key={i}><time>{new Date(e.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time><span>{e.message}</span></li>)}
            </ul>}
          </Panel>

          <Panel title="Fallback" subtitle="No signal in the room? Finish the call step manually.">
            <div className="inline-actions">
              <input className="live-time-input" value={simTime} onChange={(e) => setSimTime(e.target.value)} aria-label="Appointment time" placeholder="14:30" />
              <Button variant="secondary" size="sm" onClick={() => void simulate()} disabled={busy !== '' || done}>
                <FlaskConical size={14} /> {busy === 'simulate' ? 'Finishing…' : 'Simulate call complete'}
              </Button>
            </div>
          </Panel>
        </section>
      </div>
    </div>
  );
}
