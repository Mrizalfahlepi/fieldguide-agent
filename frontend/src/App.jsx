import { useState, useCallback } from 'react';
import CameraStream from './components/CameraStream';
import AudioHandler from './components/AudioHandler';
import StatusPanel from './components/StatusPanel';
import { useWebSocket } from './hooks/useWebSocket';

const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const WS_URL = `${wsProtocol}://${window.location.host}/ws`;

export default function App() {
  const [isStreaming, setIsStreaming] = useState(false);
  const { status, aiText, isAiSpeaking, connect, disconnect, sendMessage, getAudioContext } = useWebSocket(WS_URL);

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
            <AudioHandler isActive={isStreaming} onAudioChunk={handleAudioChunk} isAiSpeaking={isAiSpeaking} />
            <StatusPanel connectionStatus={status} aiText={aiText} isStreaming={isStreaming} />
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full px-6 text-center">
            <div className="text-6xl mb-4">&#128295;</div>
            <h2 className="text-xl font-bold text-white mb-2">Welcome to FieldGuide</h2>
            <p className="text-gray-400 text-sm mb-6">
              Point your camera at any broken equipment and I will guide you through the repair step-by-step.
            </p>
            <div className="text-gray-500 text-xs space-y-1">
              <p>Water pumps, generators, electrical panels</p>
              <p>Motorcycle engines, household appliances</p>
              <p>Real-time voice guidance with safety alerts</p>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 shrink-0">
        {!isStreaming ? (
          <button onClick={handleStart} className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold text-base">
            &#128247; Start Repair Session
          </button>
        ) : (
          <button onClick={handleStop} className="w-full py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold text-base">
            Stop Session
          </button>
        )}
      </div>
    </div>
  );
}
