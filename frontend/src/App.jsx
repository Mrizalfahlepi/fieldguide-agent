import { useState, useCallback } from 'react';
import CameraStream from './components/CameraStream';
import AudioHandler from './components/AudioHandler';
import StatusPanel from './components/StatusPanel';
import { useWebSocket } from './hooks/useWebSocket';

const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const WS_URL = `${wsProtocol}://${window.location.host}/ws/session`;


export default function App() {
  const [isStreaming, setIsStreaming] = useState(false);
  const { status, aiText, connect, disconnect, sendMessage, getAudioContext } = useWebSocket(WS_URL);

  const handleStart = useCallback(() => { connect(); setIsStreaming(true); }, [connect]);
  const handleStop = useCallback(() => { disconnect(); setIsStreaming(false); }, [disconnect]);
  const handleVideoFrame = useCallback((b64) => { sendMessage('video', b64); }, [sendMessage]);
  const handleAudioChunk = useCallback((b64) => { sendMessage('audio', b64); }, [sendMessage]);

  return (
    <div className="h-full w-full flex flex-col bg-fg-dark">
      <header className="bg-fg-primary px-4 py-3 flex items-center justify-between z-30 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-2xl">&#128295;</span>
          <div>
            <h1 className="text-lg font-bold text-white leading-tight">FieldGuide</h1>
            <p className="text-[10px] text-blue-200 leading-tight">AI Visual Repair Supervisor</p>
          </div>
        </div>
        {isStreaming && (
          <div className="flex items-center gap-1.5 bg-red-500/20 rounded-full px-3 py-1">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            <span className="text-xs text-red-200">LIVE</span>
          </div>
        )}
      </header>

      <div className="flex-1 relative overflow-hidden">
        {isStreaming ? (
          <>
            <CameraStream isActive={isStreaming} onFrame={handleVideoFrame} />
            <AudioHandler isActive={isStreaming && status === 'connected'} onAudioChunk={handleAudioChunk} />
            <StatusPanel connectionStatus={status} aiText={aiText} isStreaming={isStreaming} />
            <div className="absolute inset-0 z-10 pointer-events-none">
              <div className="w-full h-full border border-white/10">
                <div className="absolute top-1/3 left-0 right-0 border-t border-white/10" />
                <div className="absolute top-2/3 left-0 right-0 border-t border-white/10" />
                <div className="absolute top-0 bottom-0 left-1/3 border-l border-white/10" />
                <div className="absolute top-0 bottom-0 left-2/3 border-l border-white/10" />
              </div>
            </div>
          </>
        ) : (
          <div className="h-full flex flex-col items-center justify-center px-8 text-center">
            <div className="text-7xl mb-6">&#128295;</div>
            <h2 className="text-2xl font-bold text-white mb-3">Welcome to FieldGuide</h2>
            <p className="text-gray-400 mb-2 max-w-sm">Point your camera at any broken equipment and I will guide you through the repair step-by-step.</p>
            <div className="mt-6 space-y-2 text-left text-sm text-gray-500">
              <p>Water pumps, generators, electrical panels</p>
              <p>Motorcycle engines, household appliances</p>
              <p>Real-time voice guidance with safety alerts</p>
            </div>
          </div>
        )}
      </div>

      <div className="bg-gray-800/90 backdrop-blur px-4 py-4 shrink-0 z-30">
        {!isStreaming ? (
          <button onClick={handleStart} className="w-full bg-fg-primary hover:bg-blue-700 text-white font-bold py-4 rounded-2xl text-lg flex items-center justify-center gap-2">
            &#128247; Start Repair Session
          </button>
        ) : (
          <button onClick={handleStop} className="w-full bg-fg-danger hover:bg-red-700 text-white font-bold py-4 rounded-2xl text-lg flex items-center justify-center gap-2">
            Stop Session
          </button>
        )}
      </div>
    </div>
  );
}
