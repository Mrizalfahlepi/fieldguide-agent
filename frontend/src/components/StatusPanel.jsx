export default function StatusPanel({ connectionStatus, aiText, isStreaming }) {
  const colors = { disconnected: 'bg-red-500', connecting: 'bg-yellow-500', connected: 'bg-green-500' };
  const labels = { disconnected: 'Disconnected', connecting: 'Connecting...', connected: 'AI Connected' };

  return (
    <>
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2 bg-black/60 rounded-full px-3 py-1.5">
        <div className={`w-2.5 h-2.5 rounded-full ${colors[connectionStatus]} ${connectionStatus === 'connected' ? 'animate-pulse' : ''}`} />
        <span className="text-xs text-white/80">{labels[connectionStatus]}</span>
      </div>
      {isStreaming && (
        <div className="absolute bottom-24 left-0 right-0 z-20 flex justify-center px-4">
          <div className="bg-black/70 backdrop-blur-sm rounded-2xl px-5 py-3 max-w-sm">
            {aiText ? (
              <p className="text-sm text-white text-center">{aiText}</p>
            ) : (
              <div className="flex items-center gap-2 justify-center">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-fg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-fg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-fg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-sm text-white/70">Listening and Watching...</span>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
