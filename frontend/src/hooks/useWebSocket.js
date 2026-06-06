import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * useWebSocket — manages WebSocket lifecycle and audio playback.
 *
 * KEY FIXES:
 *
 * 1. INTERRUPTION HANDLING: When server sends "interrupted", we now
 *    immediately flush the audio queue AND stop the currently playing
 *    audio source. Previously, old audio would keep playing even after
 *    the user interrupted, making it seem like the AI wasn't listening.
 *
 * 2. AUDIO QUEUE FLUSH: Added proper queue flush on interrupted and
 *    on disconnect. Prevents stale audio from playing after state changes.
 *
 * 3. RECONNECT BACKOFF: Increased max attempts from 10 to 15 with
 *    better exponential backoff for unstable mobile connections.
 */
export function useWebSocket(url) {
  const [status, setStatus] = useState('disconnected');
  const [aiText, setAiText] = useState('');
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);
  const wsRef = useRef(null);
  const reconnectCount = useRef(0);
  const audioQueueRef = useRef([]);
  const audioContextRef = useRef(null);
  const isPlayingRef = useRef(false);
  const currentSourceRef = useRef(null);

  const getAudioContext = useCallback(() => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    }
    // Resume if suspended (browsers require user gesture to start audio)
    if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume().catch(() => {});
    }
    return audioContextRef.current;
  }, []);

  const flushAudioQueue = useCallback(() => {
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    // Stop currently playing audio source
    if (currentSourceRef.current) {
      try {
        currentSourceRef.current.onended = null;
        currentSourceRef.current.stop();
      } catch (e) {
        // Already stopped, ignore
      }
      currentSourceRef.current = null;
    }
  }, []);

  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      return;
    }
    isPlayingRef.current = true;
    const audioB64 = audioQueueRef.current.shift();
    try {
      const ctx = getAudioContext();
      const raw = atob(audioB64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      const int16 = new Int16Array(bytes.buffer);
      const audioBuffer = ctx.createBuffer(1, int16.length, 24000);
      const channelData = audioBuffer.getChannelData(0);
      for (let i = 0; i < int16.length; i++) channelData[i] = int16[i] / 32768.0;
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;

      // Amplify output volume (Gemini audio is quiet by default)
      const gainNode = ctx.createGain();
      gainNode.gain.value = 4.0; // 4x amplification
      source.connect(gainNode);
      gainNode.connect(ctx.destination);
      currentSourceRef.current = source;
      source.onended = () => {
        currentSourceRef.current = null;
        isPlayingRef.current = false;
        playNextAudio();
      };
      source.start();
    } catch (e) {
      console.error('Audio playback error:', e);
      currentSourceRef.current = null;
      isPlayingRef.current = false;
      playNextAudio();
    }
  }, [getAudioContext]);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    setStatus('connecting');
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      reconnectCount.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'audio') {
          audioQueueRef.current.push(msg.data);
          playNextAudio();

        } else if (msg.type === 'ai_speaking') {
          setIsAiSpeaking(msg.speaking);

        } else if (msg.type === 'transcript') {
          if (msg.role === 'assistant') {
            setAiText(msg.text);
          }

        } else if (msg.type === 'status') {
          setAiText(msg.text || msg.message || '');

        } else if (msg.type === 'turn_complete') {
          // Keep last text visible briefly then clear
          setTimeout(() => setAiText(''), 3000);

        } else if (msg.type === 'interrupted') {
          // FIX: Immediately flush audio queue and stop playback
          // This prevents the AI from "talking over" the user after interrupt
          setIsAiSpeaking(false);
          flushAudioQueue();

        } else if (msg.type === 'error') {
          setAiText('Error: ' + msg.message);
        }
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      setIsAiSpeaking(false);
      if (reconnectCount.current < 15) {
        reconnectCount.current++;
        const delay = Math.min(1000 * Math.pow(1.5, reconnectCount.current - 1), 15000);
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => { ws.close(); };
  }, [url, playNextAudio, flushAudioQueue]);

  const disconnect = useCallback(() => {
    reconnectCount.current = 99;
    if (wsRef.current) {
      try { wsRef.current.send(JSON.stringify({ type: 'end_session' })); } catch (e) {}
      wsRef.current.close();
    }
    setStatus('disconnected');
    setIsAiSpeaking(false);
    flushAudioQueue();
  }, [flushAudioQueue]);

  const sendMessage = useCallback((type, data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      if (type === 'text') {
        wsRef.current.send(JSON.stringify({ type, text: data }));
      } else {
        wsRef.current.send(JSON.stringify({ type, data }));
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      reconnectCount.current = 99;
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return { status, aiText, isAiSpeaking, connect, disconnect, sendMessage, getAudioContext };
}
