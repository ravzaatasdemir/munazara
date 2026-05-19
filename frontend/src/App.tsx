/**
 * Münazara — React Frontend
 * FastAPI backend ile SSE üzerinden iletişim kurar.
 *
 * Env variables:
 *   VITE_API_URL  → Backend URL (default: http://localhost:8000)
 *   VITE_BG_URL   → Sınıf arka plan görseli (default: /src/assets/classroom-bg.jpg)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Menu, History, Settings, MessageSquarePlus, Headphones,
  X, Hand, Send, Play, ChevronRight, Loader2, BookOpen, AlertCircle
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

type AgentState =
  | 'idle'
  | 'starting'
  | 'teacher_speaking'
  | 'user_choices'
  | 'user_typing'
  | 'ai_speaking'
  | 'summary'
  | 'done'
  | 'error';

interface Message {
  id: string;
  role: 'professor' | 'student' | 'user';
  content: string;
}

interface OrchestratorStatus {
  current_round: number;
  max_rounds: number;
  is_finished: boolean;
  waiting_for_user: boolean;
  user_question_count: number;
  max_user_questions: number;
  questions_remaining: number;
  can_ask_question: boolean;
  last_error: string | null;
}

// ─── Config ───────────────────────────────────────────────────────────────────

const API_URL: string = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL)
  ? (import.meta as any).env.VITE_API_URL
  : 'http://localhost:8000';

const BG_URL: string = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_BG_URL)
  ? (import.meta as any).env.VITE_BG_URL
  : '/background.png';

// ─── SSE Stream Helper ────────────────────────────────────────────────────────

async function* streamPost(url: string, body: object): AsyncGenerator<any> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'API hatası');
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)); } catch { /* skip */ }
      }
    }
  }
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  const [agentState, setAgentState]       = useState<AgentState>('idle');
  const [sessionId, setSessionId]         = useState<string | null>(null);
  const [status, setStatus]               = useState<OrchestratorStatus | null>(null);
  const [messages, setMessages]           = useState<Message[]>([]);
  const [streamingRole, setStreamingRole] = useState<'professor' | 'student' | null>(null);
  const [streamingText, setStreamingText] = useState('');
  const [topic, setTopic]                 = useState('');
  const [questionInput, setQuestionInput] = useState('');
  const [summary, setSummary]             = useState('');
  const [errorMsg, setErrorMsg]           = useState('');
  const [menuExpanded, setMenuExpanded]   = useState(false);
  const [historyOpen, setHistoryOpen]     = useState(false);
  const [spotifyOpen, setSpotifyOpen]     = useState(false);
  const [demoMode, setDemoMode]           = useState(false);
  const [pastSessions, setPastSessions]   = useState<{ topic: string; messages: Message[] }[]>([]);

  const historyEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (historyOpen) historyEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, historyOpen]);

  const addMessage = (role: 'professor' | 'student' | 'user', content: string) =>
    setMessages(prev => [...prev, { id: `${Date.now()}-${Math.random()}`, role, content }]);

  // ── Start Debate ─────────────────────────────────────────────────────────

  const handleStartDebate = useCallback(async () => {
    if (!topic.trim()) return;
    setAgentState('starting');
    setMessages([]);
    setSummary('');
    setErrorMsg('');
    setStreamingText('');
    setStreamingRole('professor');

    try {
      let profText = '';
      for await (const ev of streamPost(`${API_URL}/api/start`, {
        topic: topic.trim(), max_rounds: 5, max_user_questions: 3,
      })) {
        if (ev.type === 'session_id') {
          setSessionId(ev.data);
          setAgentState('teacher_speaking');
        } else if (ev.type === 'chunk' && ev.role === 'professor') {
          profText += ev.data;
          setStreamingText(profText);
        } else if (ev.type === 'complete' && ev.role === 'professor') {
          addMessage('professor', ev.data);
          setStreamingText('');
          setStreamingRole(null);
        } else if (ev.type === 'status') {
          setStatus(ev.data);
          setAgentState('user_choices');
        } else if (ev.type === 'error') {
          throw new Error(ev.data);
        }
      }
    } catch (e: any) {
      setErrorMsg(e.message ?? 'Bağlantı hatası');
      setAgentState('error');
    }
  }, [topic]);

  // ── Skip Turn ────────────────────────────────────────────────────────────

  const handleSkip = useCallback(async () => {
    if (!sessionId) return;
    setAgentState('ai_speaking');
    setStreamingText('');

    try {
      let studentText = '';
      let profText    = '';

      for await (const ev of streamPost(`${API_URL}/api/skip`, { session_id: sessionId })) {
        if (ev.type === 'chunk') {
          setStreamingRole(ev.role);
          if (ev.role === 'student') { studentText += ev.data; setStreamingText(studentText); }
          else                       { profText    += ev.data; setStreamingText(profText); }
        } else if (ev.type === 'complete') {
          addMessage(ev.role, ev.data);
          setStreamingText('');
          if (ev.role === 'student') { profText = ''; setStreamingRole('professor'); }
        } else if (ev.type === 'status') {
          setStatus(ev.data);
          if (ev.data.is_finished) { setAgentState('summary'); await doSummary(sessionId); }
          else                     { setAgentState('user_choices'); }
        } else if (ev.type === 'error') {
          throw new Error(ev.data);
        }
      }
    } catch (e: any) {
      setErrorMsg(e.message ?? 'Bağlantı hatası');
      setAgentState('error');
    } finally {
      setStreamingRole(null);
      setStreamingText('');
    }
  }, [sessionId]);

  // ── Ask Question ─────────────────────────────────────────────────────────

  const handleSendQuestion = useCallback(async () => {
    if (!questionInput.trim() || !sessionId) return;
    const q = questionInput.trim();
    setQuestionInput('');
    addMessage('user', q);
    setAgentState('teacher_speaking');
    setStreamingRole('professor');
    setStreamingText('');

    try {
      let profText = '';
      for await (const ev of streamPost(`${API_URL}/api/ask`, { session_id: sessionId, question: q })) {
        if (ev.type === 'chunk' && ev.role === 'professor') {
          profText += ev.data;
          setStreamingText(profText);
        } else if (ev.type === 'complete' && ev.role === 'professor') {
          addMessage('professor', ev.data);
          setStreamingText('');
          setStreamingRole(null);
        } else if (ev.type === 'status') {
          setStatus(ev.data);
          if (ev.data.is_finished) { setAgentState('summary'); await doSummary(sessionId); }
          else                     { setAgentState('user_choices'); }
        } else if (ev.type === 'error') {
          throw new Error(ev.data);
        }
      }
    } catch (e: any) {
      setErrorMsg(e.message ?? 'Bağlantı hatası');
      setAgentState('error');
    }
  }, [questionInput, sessionId]);

  // ── Summary ──────────────────────────────────────────────────────────────

  const doSummary = async (sid: string) => {
    let text = '';
    try {
      const res = await fetch(`${API_URL}/api/summary/${sid}`, { method: 'POST' });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === 'chunk')            { text += ev.data; setSummary(text); }
            if (ev.type === 'summary_complete') { setSummary(ev.data || text); }
          }
        }
      }
    } catch { /* silently fail */ }
    setAgentState('done');
  };

  // ── Demo Mode ────────────────────────────────────────────────────────────

  const handleDemo = async () => {
    try {
      const res  = await fetch(`${API_URL}/api/demo`);
      const data = await res.json();
      setTopic(data.topic);
      setDemoMode(true);
      setMessages(data.messages.map((m: any, i: number) => ({
        id: `demo-${i}`, role: m.role, content: m.content,
      })));
      setAgentState('done');
    } catch (e: any) {
      setErrorMsg('Demo yüklenemedi: ' + e.message);
      setAgentState('error');
    }
  };

  // ── Reset ────────────────────────────────────────────────────────────────

  const handleReset = () => {
    if (messages.length && topic)
      setPastSessions(prev => [...prev, { topic, messages }]);
    if (sessionId)
      fetch(`${API_URL}/api/session/${sessionId}`, { method: 'DELETE' }).catch(() => {});
    setSessionId(null); setStatus(null); setMessages([]); setTopic('');
    setStreamingText(''); setStreamingRole(null); setSummary('');
    setErrorMsg(''); setDemoMode(false); setAgentState('idle');
  };

  // ── Derived display values ────────────────────────────────────────────────

  const questionsRemaining = status?.questions_remaining ?? 3;
  const currentRound       = status?.current_round ?? 0;
  const maxRounds          = status?.max_rounds ?? 5;

  const teacherBubbleText = (() => {
    if (agentState === 'starting') return 'Hazırlanıyor...';
    if ((agentState === 'teacher_speaking' || agentState === 'starting') && streamingRole === 'professor' && streamingText)
      return streamingText + '▌';
    if (agentState === 'teacher_speaking') return 'Profesör düşünüyor...';
    const last = [...messages].reverse().find(m => m.role === 'professor');
    if (last) return last.content;
    if (agentState === 'idle') return '"Evlatlarım, tartışmak istediğiniz konuyu yazın..."';
    return '';
  })();

  const studentBubbleText = (() => {
    if (agentState === 'ai_speaking' && streamingRole === 'student') return streamingText + '▌';
    return [...messages].reverse().find(m => m.role === 'student')?.content ?? '';
  })();

  const showStudentBubble = agentState === 'ai_speaking' && streamingRole === 'student' && !!streamingText;

  const isStreaming = ['starting', 'teacher_speaking', 'ai_speaking', 'summary'].includes(agentState);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen w-screen relative overflow-hidden font-pixel flex flex-col items-center">

      {/* Background */}
      <div className="absolute inset-0 bg-cover bg-center bg-no-repeat z-0"
        style={{ backgroundImage: `url('${BG_URL}')` }} />
      <div className="absolute inset-0 bg-black/30 z-0" />

      {/* Main layout */}
      <div className="relative w-full h-full flex flex-col justify-between py-6 px-4 md:px-12 pointer-events-none z-20 max-w-7xl mx-auto">

        {/* ── Teacher Bubble ── */}
        <div className="w-full flex justify-center pointer-events-auto mt-4 px-4">
          <div className="max-w-3xl w-full relative">
            <div className="pixel-border bg-surface p-4 md:p-6 pixel-shadow-lg">
              <p className="text-on-surface leading-snug whitespace-pre-wrap font-pixel text-base md:text-lg font-bold text-center min-h-[2.5rem]">
                {teacherBubbleText}
              </p>
              {(agentState === 'starting' || (agentState === 'teacher_speaking' && !streamingText)) && (
                <div className="flex justify-center mt-2">
                  <Loader2 size={20} className="animate-spin text-primary-dark" />
                </div>
              )}
            </div>
            <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 z-10">
              <div className="pixel-bubble-tail-down relative">
                <div className="pixel-bubble-tail-down-inner absolute -top-[16px] -left-[8px]" />
              </div>
            </div>
          </div>
        </div>

        {/* ── Round Progress ── */}
        {status && (
          <div className="pointer-events-auto flex justify-center mt-5">
            <div className="bg-surface/90 pixel-border px-4 py-2 flex items-center gap-4 text-sm">
              <span className="font-bold text-primary-dark">TUR {currentRound}/{maxRounds}</span>
              <div className="h-3 w-32 bg-surface-variant pixel-border overflow-hidden">
                <div className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${Math.min((currentRound / maxRounds) * 100, 100)}%` }} />
              </div>
              <span className={`font-bold ${questionsRemaining > 1 ? 'text-primary-dark' : questionsRemaining === 1 ? 'text-yellow-600' : 'text-red-600'}`}>
                ❓ {questionsRemaining} soru hakkı
              </span>
            </div>
          </div>
        )}

        {/* ── Side Menu ── */}
        <div className="absolute right-4 md:right-12 top-1/2 -translate-y-1/2 flex flex-col items-end gap-6 pointer-events-auto z-40">
          <div className="flex flex-col items-end gap-3">
            <button onClick={() => setMenuExpanded(!menuExpanded)}
              className="pixel-round-btn w-14 h-14 bg-surface text-on-surface hover:-translate-y-0.5 hover:-translate-x-0.5 hover:shadow-[6px_6px_0_0_#222222] transition-all">
              <Menu size={28} />
            </button>
            <div className={`flex flex-col items-end gap-5 transition-all duration-200 ${menuExpanded ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
              {[
                { icon: <MessageSquarePlus size={22} />, label: 'Yeni Konu', color: 'bg-primary text-on-primary', action: () => { handleReset(); setMenuExpanded(false); } },
                { icon: <History size={22} />, label: 'Geçmiş', color: 'bg-secondary text-on-surface', action: () => { setHistoryOpen(true); setMenuExpanded(false); } },
                { icon: <Settings size={22} />, label: 'Ayarlar', color: 'bg-surface text-on-surface', action: () => setMenuExpanded(false) },
              ].map(({ icon, label, color, action }) => (
                <button key={label} onClick={action} className="flex items-center gap-3 group flex-row-reverse">
                  <span className="bg-surface pixel-border px-3 py-1 text-sm opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">{label}</span>
                  <div className={`pixel-round-btn w-12 h-12 ${color} group-hover:-translate-y-0.5 group-hover:-translate-x-0.5 group-hover:shadow-[6px_6px_0_0_#222222] transition-all`}>
                    {icon}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Spotify FAB ── */}
        <div className="absolute left-4 md:left-12 bottom-6 pointer-events-auto z-40">
          <div className="relative">
            {spotifyOpen && (
              <div className="absolute bottom-full left-0 mb-4 bg-[#191414] text-white pixel-border p-4 w-64">
                <div className="flex items-center gap-4 mb-2">
                  <div className="w-12 h-12 bg-spotify rounded-sm flex items-center justify-center text-white">
                    <Headphones size={22} />
                  </div>
                  <div>
                    <p className="text-sm font-bold">Lofi Study Beats</p>
                    <p className="text-xs text-zinc-400">ChilledCow</p>
                  </div>
                </div>
                <div className="flex justify-center border-t-2 border-zinc-700 pt-2">
                  <Play size={22} className="hover:text-spotify cursor-pointer" />
                </div>
              </div>
            )}
            <button onClick={() => setSpotifyOpen(!spotifyOpen)}
              className="pixel-round-btn bg-spotify w-14 h-14 text-white hover:brightness-110 hover:-translate-y-0.5 hover:-translate-x-0.5 hover:shadow-[6px_6px_0_0_#222222] transition-all">
              <Headphones size={30} />
            </button>
          </div>
        </div>

        {/* ── Bottom ── */}
        <div className="flex flex-col items-center w-full mt-auto gap-4 pointer-events-none mb-2">

          {/* Student Bubble */}
          <div className={`w-full flex justify-end px-4 md:px-12 transition-all duration-300 ${showStudentBubble ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
            <div className="pixel-border bg-surface-variant p-4 pixel-shadow-lg max-w-sm pointer-events-auto max-h-32 overflow-y-auto">
              <p className="text-on-surface text-sm font-pixel">
                <span className="font-bold text-secondary-dark text-base">Kamil: </span>
                {studentBubbleText}
              </p>
            </div>
          </div>

          {/* Interaction Panel */}
          <div className="w-full md:max-w-4xl bg-surface/95 backdrop-blur-sm pixel-border pixel-shadow-lg pointer-events-auto">

            {/* IDLE */}
            {agentState === 'idle' && (
              <div className="p-4 md:p-6">
                <p className="text-center text-on-surface-variant text-sm mb-3">Bir kavram yazın ve tartışmayı başlatın</p>
                <div className="flex gap-3">
                  <input
                    type="text" value={topic} onChange={e => setTopic(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleStartDebate()}
                    placeholder="ör: Türev nedir, Fotosentez, Arz ve Talep..."
                    className="flex-1 pixel-input bg-surface border-4 border-on-surface px-4 py-3 text-base"
                    autoFocus
                  />
                  <button onClick={handleStartDebate} disabled={!topic.trim()}
                    className="pixel-btn bg-primary text-on-primary-dark px-5 py-3 disabled:opacity-40">
                    <Send size={22} />
                  </button>
                </div>
                <div className="flex justify-center mt-3">
                  <button onClick={handleDemo} className="text-sm text-secondary-dark underline font-sans hover:text-primary-dark">
                    🎬 Demo'yu göster (API key gerektirmez)
                  </button>
                </div>
              </div>
            )}

            {/* LOADING states */}
            {(agentState === 'starting' || agentState === 'ai_speaking' || agentState === 'summary') && (
              <div className="p-6 flex items-center justify-center gap-3 h-24">
                <Loader2 size={22} className="animate-spin text-primary-dark" />
                <span className="text-on-surface-variant font-sans text-base animate-pulse">
                  {agentState === 'starting' ? 'Profesör hazırlanıyor...'
                    : agentState === 'summary' ? 'Öğrenme özeti hazırlanıyor...'
                    : 'Kamil ve Profesör konuşuyor...'}
                </span>
              </div>
            )}

            {/* TEACHER SPEAKING */}
            {agentState === 'teacher_speaking' && (
              <div className="p-6 flex items-center justify-center gap-3 h-24">
                <Loader2 size={22} className="animate-spin text-primary-dark" />
                <span className="text-on-surface-variant font-sans text-base animate-pulse">Profesör yanıtlıyor...</span>
              </div>
            )}

            {/* USER CHOICES */}
            {agentState === 'user_choices' && (
              <div className="p-4 md:p-6 flex items-center gap-4 w-full justify-center h-24">
                <button
                  onClick={() => setAgentState('user_typing')}
                  disabled={questionsRemaining <= 0}
                  className="pixel-btn bg-primary text-on-primary-dark px-5 py-4 flex items-center gap-2 text-base w-52 justify-center disabled:opacity-40 disabled:cursor-not-allowed uppercase"
                >
                  <Hand size={18} fill="currentColor" strokeWidth={1} />
                  Soru Sor ({questionsRemaining})
                </button>
                <div className="w-1 h-12 bg-on-surface opacity-20" />
                <button
                  onClick={handleSkip}
                  className="pixel-btn bg-surface border-secondary-dark text-secondary-dark hover:bg-secondary transition-colors px-5 py-4 flex items-center gap-2 text-base w-52 justify-center uppercase"
                >
                  Kamil Sorsun
                  <ChevronRight size={18} strokeWidth={3} />
                </button>
              </div>
            )}

            {/* USER TYPING */}
            {agentState === 'user_typing' && (
              <div className="p-4 flex items-center gap-3 w-full h-24">
                <input
                  type="text" value={questionInput}
                  onChange={e => setQuestionInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSendQuestion()}
                  placeholder="Profesöre soru sor..."
                  className="flex-1 pixel-input bg-surface border-4 border-on-surface px-4 py-3 text-base"
                  autoFocus
                />
                <button onClick={handleSendQuestion} className="pixel-btn bg-primary text-on-primary-dark p-3">
                  <Send size={26} />
                </button>
                <button onClick={() => setAgentState('user_choices')} className="pixel-btn bg-surface p-3 opacity-70 hover:opacity-100">
                  <X size={26} />
                </button>
              </div>
            )}

            {/* DONE */}
            {agentState === 'done' && (
              <div className="p-4 flex flex-col gap-3">
                {summary && (
                  <div className="bg-surface-variant pixel-border p-4 max-h-48 overflow-y-auto">
                    <div className="flex items-center gap-2 mb-2">
                      <BookOpen size={16} className="text-primary-dark" />
                      <span className="font-bold text-primary-dark font-pixel">Öğrenme Özeti</span>
                    </div>
                    <p className="text-on-surface leading-relaxed whitespace-pre-wrap font-sans text-sm">{summary}</p>
                  </div>
                )}
                {demoMode && (
                  <p className="text-center text-xs text-secondary-dark font-sans">🎬 Demo modu — gerçek API kullanılmadı</p>
                )}
                <button onClick={handleReset}
                  className="pixel-btn bg-primary text-on-primary-dark py-3 px-6 text-base self-center uppercase">
                  🔄 Yeni Konu Başlat
                </button>
              </div>
            )}

            {/* ERROR */}
            {agentState === 'error' && (
              <div className="p-6 flex flex-col items-center gap-3">
                <div className="flex items-center gap-2 text-red-600 font-sans">
                  <AlertCircle size={20} />
                  <span className="text-sm">{errorMsg}</span>
                </div>
                <button onClick={handleReset} className="pixel-btn bg-surface text-on-surface text-sm px-4 py-2">
                  Başa Dön
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── History Slide Panel ── */}
      <div className={`absolute right-0 top-0 bottom-0 w-full sm:w-96 bg-surface pixel-border border-r-0 border-y-0 z-50 transform transition-transform duration-300 flex flex-col ${historyOpen ? 'translate-x-0 shadow-[-16px_0_30px_rgba(0,0,0,0.3)]' : 'translate-x-full'}`}>
        <div className="p-4 border-b-4 border-on-surface bg-surface-variant flex justify-between items-center">
          <h2 className="text-lg flex items-center gap-2 font-bold">
            <History size={22} /> Konuşma Geçmişi
          </h2>
          <button onClick={() => setHistoryOpen(false)} className="hover:bg-surface p-2 border-2 border-transparent hover:border-on-surface transition-colors">
            <X size={22} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 font-sans text-sm">
          {messages.length > 0 && (
            <>
              <p className="text-xs text-secondary-dark font-bold uppercase tracking-wider">Aktif: {topic}</p>
              {messages.map(msg => (
                <div key={msg.id} className="bg-surface-variant p-3 pixel-border">
                  <span className={`font-pixel font-bold ${msg.role === 'user' ? 'text-primary-dark' : msg.role === 'professor' ? 'text-on-surface' : 'text-secondary-dark'}`}>
                    {msg.role === 'user' ? 'Sen' : msg.role === 'professor' ? 'Hoca' : 'Kamil'}:
                  </span>
                  <p className="mt-1 leading-relaxed text-on-surface">{msg.content}</p>
                </div>
              ))}
            </>
          )}
          {pastSessions.map((s, i) => (
            <details key={i} className="pixel-border p-2">
              <summary className="cursor-pointer font-bold text-secondary-dark text-xs">📖 {s.topic}</summary>
              <div className="mt-2 flex flex-col gap-2">
                {s.messages.map(m => (
                  <div key={m.id} className="bg-surface-variant p-2 text-xs">
                    <span className="font-bold">{m.role === 'user' ? 'Sen' : m.role === 'professor' ? 'Hoca' : 'Kamil'}: </span>
                    {m.content.slice(0, 100)}{m.content.length > 100 ? '...' : ''}
                  </div>
                ))}
              </div>
            </details>
          ))}
          {messages.length === 0 && pastSessions.length === 0 && (
            <p className="text-center text-on-surface-variant py-8 text-sm">Henüz konuşma yok</p>
          )}
          <div ref={historyEndRef} />
        </div>
      </div>
    </div>
  );
}
