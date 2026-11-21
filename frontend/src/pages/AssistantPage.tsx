import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Bot, GraduationCap, HeartPulse, Languages, Landmark, MessageCircle, RotateCcw, Sparkles, UserRound } from 'lucide-react';
import type { ChatHistoryItem, ChatLanguage, Topic, TopicInfo } from '../api/types';
import { endpoints } from '../api/client';
import { Button, Notice } from '../components/UI';
import { RichText, SpeakButton } from '../components/RichText';

interface VisibleMessage extends ChatHistoryItem {
  id: string;
  mock?: boolean;
  model?: string;
  language?: 'en' | 'hu';
  topic?: Topic;
}

const WELCOME: Record<'en' | 'hu', string> = {
  en: "Hi, I'm Sera. Ask me about healthcare, university, immigration or Hungarian translations. Pick a topic on the right for better answers.",
  hu: 'Szia, Sera vagyok. Kérdezz egészségügyről, egyetemről, bevándorlásról vagy fordításról. Válassz témát a jobb oldalon.',
};

const TOPIC_ICONS: Record<Topic, JSX.Element> = {
  general: <MessageCircle size={15} />,
  healthcare: <HeartPulse size={15} />,
  university: <GraduationCap size={15} />,
  immigration: <Landmark size={15} />,
  translation: <Languages size={15} />,
};

const FALLBACK_TOPICS: TopicInfo[] = [
  { id: 'healthcare', label: { en: 'Healthcare', hu: 'Egészségügy' }, examples: { en: ['How do I get a TAJ card?'] } },
  { id: 'university', label: { en: 'University', hu: 'Egyetem' }, examples: { en: ['How do I register for exams in Neptun?'] } },
  { id: 'immigration', label: { en: 'Immigration', hu: 'Bevándorlás' }, examples: { en: ['How do I renew my residence permit?'] } },
  { id: 'translation', label: { en: 'Translation', hu: 'Fordítás' }, examples: { en: ['Write an email to my landlord: the heating is broken.'] } },
];

function welcome(lang: 'en' | 'hu'): VisibleMessage {
  return { id: 'welcome', role: 'assistant', content: WELCOME[lang], language: lang };
}

export function AssistantPage() {
  const [language, setLanguage] = useState<ChatLanguage>('auto');
  const uiLang: 'en' | 'hu' = language === 'hu' ? 'hu' : 'en';
  const [topic, setTopic] = useState<Topic>('general');
  const [topics, setTopics] = useState<TopicInfo[]>(FALLBACK_TOPICS);
  const [messages, setMessages] = useState<VisibleMessage[]>([welcome('en')]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [mockMode, setMockMode] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endpoints.topics().then(setTopics).catch(() => undefined); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, sending]);
  useEffect(() => {
    setMessages((current) => (current.length === 1 && current[0].id === 'welcome' ? [welcome(uiLang)] : current));
  }, [uiLang]);

  async function sendMessage(messageText = input, topicOverride?: Topic) {
    const message = messageText.trim();
    if (!message || sending) return;
    const useTopic = topicOverride ?? topic;
    setError('');
    setInput('');
    const history: ChatHistoryItem[] = messages.filter((m) => m.id !== 'welcome').map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', content: message }]);
    setSending(true);
    try {
      const r = await endpoints.askSera({ message, language, topic: useTopic, history });
      setMockMode(r.mock);
      setMessages((current) => [...current, {
        id: `assistant-${Date.now()}`, role: 'assistant', content: r.reply,
        mock: r.mock, model: r.model, language: r.language, topic: r.topic,
      }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sera could not respond. Please try again.');
    } finally {
      setSending(false);
    }
  }

  function resetConversation() {
    setMessages([welcome(uiLang)]);
    setError('');
    setMockMode(null);
  }

  const activeTopic = topics.find((t) => t.id === topic);
  const examples = activeTopic
    ? (uiLang === 'hu' && activeTopic.examples.hu?.length ? activeTopic.examples.hu : activeTopic.examples.en)
    : topics.flatMap((t) => (uiLang === 'hu' && t.examples.hu?.length ? t.examples.hu : t.examples.en).slice(0, 1));

  return (
    <div className="page-stack assistant-page">
      <div className="page-heading-row">
        <div><div className="eyebrow"><span className="eyebrow-line" /> STUDENT LIFE IN HUNGARY</div><h1>Ask Sera</h1><p className="page-lede">Healthcare, university, immigration and Hungarian translations, in English or Hungarian.</p></div>
        <div className="assistant-controls">
          <div className="lang-switch" role="group" aria-label="Answer language">
            {(['auto', 'en', 'hu'] as ChatLanguage[]).map((l) => (
              <button key={l} type="button" className={language === l ? 'active' : ''} onClick={() => setLanguage(l)}>
                {l === 'auto' ? 'Auto' : l.toUpperCase()}
              </button>
            ))}
          </div>
          <Button variant="secondary" onClick={resetConversation}><RotateCcw size={15} /> New conversation</Button>
        </div>
      </div>

      <div className="topic-chips" role="group" aria-label="Topic">
        <button type="button" className={topic === 'general' ? 'active' : ''} onClick={() => setTopic('general')}>{TOPIC_ICONS.general} {uiLang === 'hu' ? 'Általános' : 'General'}</button>
        {topics.map((t) => (
          <button key={t.id} type="button" className={topic === t.id ? 'active' : ''} onClick={() => setTopic(t.id)}>
            {TOPIC_ICONS[t.id]} {t.label[uiLang]}
          </button>
        ))}
      </div>

      <div className="chat-layout">
        <section className="chat-panel">
          <div className="chat-header"><div className="chat-agent-mark"><Sparkles size={18} /></div><div><strong>Sera</strong><span><i /> {activeTopic ? activeTopic.label[uiLang] : (uiLang === 'hu' ? 'Általános' : 'General')} · {language === 'auto' ? 'Auto language' : language.toUpperCase()}</span></div>{mockMode !== null && <span className={`mock-indicator ${mockMode ? 'is-mock' : 'is-live'}`}>{mockMode ? 'Mock mode' : 'AI response'}</span>}</div>
          <div className="chat-messages">
            {messages.map((message) => <div className={`chat-message ${message.role}`} key={message.id}>
              <div className="chat-message-avatar">{message.role === 'assistant' ? <Bot size={17} /> : <UserRound size={17} />}</div>
              <div className="chat-message-content">
                <div className="chat-message-bubble">{message.role === 'assistant' ? <RichText text={message.content} /> : message.content}</div>
                {message.role === 'assistant' && message.id !== 'welcome' && <div className="chat-message-meta">
                  <SpeakButton text={message.content} language={message.language ?? 'en'} />
                  <span>{message.mock ? 'Mock response' : message.model}</span>
                </div>}
              </div>
            </div>)}
            {sending && <div className="chat-message assistant"><div className="chat-message-avatar"><Bot size={17} /></div><div className="chat-message-content"><div className="typing-indicator"><i /><i /><i /></div><span className="chat-message-meta">{uiLang === 'hu' ? 'Sera gondolkodik…' : 'Sera is thinking…'}</span></div></div>}
            <div ref={bottomRef} />
          </div>
          {error && <div className="chat-error"><Notice tone="danger">{error}</Notice></div>}
          <div className="chat-composer"><form onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}><input value={input} onChange={(event) => setInput(event.target.value)} placeholder={uiLang === 'hu' ? 'Írd ide a kérdésed…' : 'Ask about healthcare, university, immigration…'} disabled={sending} /><Button type="submit" disabled={sending || !input.trim()} aria-label="Send message"><ArrowUp size={17} /></Button></form><span>Sera is not a lawyer or official. Always confirm important steps with the official source.</span></div>
        </section>
        <aside className="chat-sidebar">
          <div className="suggestion-card"><span className="suggestion-kicker">{uiLang === 'hu' ? 'PRÓBÁLD KI' : 'TRY ASKING'}</span>{examples.map((suggestion) => <button key={suggestion} onClick={() => void sendMessage(suggestion)} disabled={sending}>{suggestion}<ArrowUp size={13} /></button>)}</div>
          <div className="chat-context-card"><div className="context-card-icon"><MessageCircle size={18} /></div><strong>Verified knowledge</strong><p>Answers use the team's verified notes on TAJ, residence permits, Neptun and the student card, with sources.</p></div>
          <div className="chat-boundary-note"><strong>Important</strong><p>Rules and deadlines change. For immigration, check oif.gov.hu or your international office. Emergency: 112.</p></div>
        </aside>
      </div>
    </div>
  );
}
