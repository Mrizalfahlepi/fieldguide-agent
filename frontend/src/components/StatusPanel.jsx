export default function StatusPanel({ connectionStatus, aiText, isStreaming, isAiSpeaking }) {
  const statusConfig = {
    disconnected: { dot: 'bg-red-500', label: 'Disconnected', ring: 'border-red-500/30 bg-red-500/10' },
    connecting:   { dot: 'bg-yellow-400 animate-pulse', label: 'Connecting…', ring: 'border-yellow-400/30 bg-yellow-400/10' },
    connected:    { dot: 'bg-green-400 animate-pulse-slow', label: 'AI Connected', ring: 'border-green-400/30 bg-green-400/10' },
  };
  const cfg = statusConfig[connectionStatus] ?? statusConfig.disconnected;

  return (
    <>
      {/* Connection status badge — top right */}
      <div className={`absolute top-4 right-4 z-20 flex items-center gap-2 rounded-full px-3 py-1.5 border ${cfg.ring}`}>
        <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
        <span className="text-xs text-white/80 font-medium">{cfg.label}</span>
      </div>

      {/* AI speaking indicator — top left */}
      {isAiSpeaking && (
        <div className="absolute top-4 left-4 z-20 flex items-center gap-2 glass rounded-full px-3 py-1.5 animate-fade-in">
          <div className="flex items-end gap-0.5 h-4">
            {[0, 150, 300, 150, 0].map((delay, i) => (
              <div
                key={i}
                className="wave-bar"
                style={{ height: '100%', animationDelay: `${delay}ms` }}
              />
            ))}
          </div>
          <span className="text-xs text-indigo-300 font-medium">AI Speaking</span>
        </div>
      )}

      {/* AI text panel — bottom */}
      {isStreaming && (
        <div className="absolute bottom-4 left-4 right-4 z-20 animate-slide-up">
          <div className="glass rounded-2xl px-4 py-3 min-h-[52px] flex items-center justify-center">
            {aiText ? (
              <p className="text-sm text-white text-center leading-relaxed font-medium">
                {aiText}
              </p>
            ) : (
              <div className="flex items-center gap-3">
                <div className="dot-loader flex gap-1.5">
                  {[0, 200, 400].map((delay, i) => (
                    <span key={i} style={{ animationDelay: `${delay}ms` }} />
                  ))}
                </div>
                <span className="text-xs text-fg-muted">
                  {connectionStatus === 'connected' ? 'Listening & watching…' : 'Connecting to AI…'}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
