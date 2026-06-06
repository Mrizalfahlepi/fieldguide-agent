import { useState, useCallback } from 'react';
import CameraStream from './components/CameraStream';
import AudioHandler from './components/AudioHandler';
import StatusPanel from './components/StatusPanel';
import { useWebSocket } from './hooks/useWebSocket';

const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const WS_URL = `${wsProtocol}://${window.location.host}/ws`;

const FEATURES = [
  { icon: '⚡', label: 'Real-time AI Vision' },
  { icon: '🔊', label: 'Voice Guidance' },
  { icon: '🛡️', label: 'Safety Alerts' },
  { icon: '📖', label: '11 Equipment Manuals' },
];

const SUPPORTED = [
  'Water pumps & generators',
  'Electrical panels & wiring',
  'Motorcycle engines',
  'Household appliances & fans',
];

export default function App() {
  const [isStreaming, setIsStreaming] = useState(false);
  const { status, aiText, isAiSpeaking, connect, disconnect, sendMessage } = useWebSocket(WS_URL);

  const handleStart = useCallback(() => { connect(); setIsStreaming(true); }, [connect]);
  const handleStop = useCallback(() => { disconnect(); setIsStreaming(false); }, [disconnect]);
  const handleVideoFrame = useCallback((b64) => { sendMessage('video', b64); }, [sendMessage]);
  const handleAudioChunk = useCallback((b64) => { sendMessage('audio', b64); }, [sendMessage]);

  return (
    <div className="h-full w-full flex flex-col bg-fg-dark font-sans">

      {/* ── Header ── */}
      <header className="glass-dark shrink-0 z-30 px-5 py-3 flex items-center justify-between border-b border-fg-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl btn-brand flex items-center justify-center text-base shadow-lg animate-glow">
            🔧
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide leading-none">FieldGuide <span className="gradient-text">AI</span></h1>
            <p className="text-[10px] text-fg-muted leading-none mt-0.5">Visual Repair Supervisor</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isStreaming ? (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-full px-3 py-1">
              <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              <span className="text-xs text-red-400 font-medium">LIVE</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 bg-fg-card border border-fg-border rounded-full px-3 py-1">
              <div className="w-1.5 h-1.5 bg-fg-muted rounded-full" />
              <span className="text-xs text-fg-muted">Standby</span>
            </div>
          )}
        </div>
      </header>

      {/* ── Main Content ── */}
      <div className="flex-1 relative overflow-hidden">
        {isStreaming ? (
          <>
            <CameraStream isActive={isStreaming} onFrame={handleVideoFrame} />
            <AudioHandler isActive={isStreaming} onAudioChunk={handleAudioChunk} isAiSpeaking={isAiSpeaking} />
            <StatusPanel connectionStatus={status} aiText={aiText} isStreaming={isStreaming} isAiSpeaking={isAiSpeaking} />
          </>
        ) : (
          <WelcomeScreen />
        )}
      </div>

      {/* ── Bottom Action ── */}
      <div className="shrink-0 p-4 glass-dark border-t border-fg-border">
        {!isStreaming ? (
          <button
            onClick={handleStart}
            className="btn-brand w-full py-3.5 rounded-2xl text-white font-semibold text-sm tracking-wide flex items-center justify-center gap-2"
          >
            <span className="text-base">📷</span>
            Start Repair Session
          </button>
        ) : (
          <button
            onClick={handleStop}
            className="btn-danger w-full py-3.5 rounded-2xl font-semibold text-sm tracking-wide flex items-center justify-center gap-2"
          >
            <span className="text-base">⏹</span>
            End Session
          </button>
        )}
      </div>
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="relative h-full flex flex-col items-center justify-center px-6 bg-fg-dark bg-grid overflow-hidden">
      {/* Ambient glow orbs */}
      <div className="orb w-64 h-64 bg-blue-600/20 top-[-60px] left-[-60px]" />
      <div className="orb w-48 h-48 bg-indigo-600/15 bottom-[-40px] right-[-40px]" />

      <div className="relative z-10 w-full max-w-sm animate-fade-in">

        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="relative">
            <div className="w-20 h-20 rounded-3xl btn-brand flex items-center justify-center text-4xl shadow-2xl animate-glow">
              🔧
            </div>
            <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-green-500 rounded-full border-2 border-fg-dark flex items-center justify-center text-xs">
              ✓
            </div>
          </div>
        </div>

        {/* Headline */}
        <div className="text-center mb-6">
          <h2 className="text-2xl font-extrabold text-white leading-tight mb-2">
            Your AI Repair<br />
            <span className="gradient-text">Supervisor</span>
          </h2>
          <p className="text-sm text-fg-muted leading-relaxed">
            Point your camera at any broken equipment. I'll guide you through the fix step-by-step, in real time.
          </p>
        </div>

        {/* Feature chips */}
        <div className="grid grid-cols-2 gap-2 mb-6">
          {FEATURES.map((f) => (
            <div key={f.label} className="feature-chip rounded-xl px-3 py-2 flex items-center gap-2">
              <span className="text-sm">{f.icon}</span>
              <span className="text-xs font-medium text-blue-200">{f.label}</span>
            </div>
          ))}
        </div>

        {/* Supported equipment */}
        <div className="glass rounded-2xl p-4">
          <p className="text-xs font-semibold text-fg-muted uppercase tracking-widest mb-3">Supported Equipment</p>
          <div className="space-y-2">
            {SUPPORTED.map((s) => (
              <div key={s} className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                <span className="text-xs text-slate-300">{s}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
