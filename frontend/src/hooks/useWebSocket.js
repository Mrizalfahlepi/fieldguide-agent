import { useState, useRef, useCallback, useEffect } from 'react';

export function useWebSocket(url) {
  const [status, setStatus] = useState('disconnected');
  const [aiText, setAiText] = useState('');
  const wsRef = useRef(null);
  const reconnectCount = useRef(0);
  const audioQueueRef = useRef([]);
  const audioContextRef = useRef(null);
  const isPlayingRef = useRef(false);

  const getAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    }
    return audioContextRef.current;
  }, []);

  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;
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
      source.connect(ctx.destination);
      source.onended = () => { isPlayingRef.current = false; playNextAudio(); };
      source.start();
    } catch (e) {
      console.error('Audio playback error:', e);
      isPlayingRef.current = false;
      playNextAudio();
    }
  }, [getAudioContext]);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    setStatus('connecting');
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => { setStatus('connected'); reconnectCount.current = 0; };
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'audio') { audioQueueRef.current.push(msg.data); playNextAudio(); }
        else if (msg.type === 'status') { setAiText(msg.text || msg.message); }
        else if (msg.type === 'turn_complete') { setAiText(''); }
        else if (msg.type === 'error') { setAiText('Error: ' + msg.message); }
      } catch (e) { console.error('[WS] Parse error:', e); }
    };
    ws.onclose = () => {
      setStatus('disconnected');
      if (reconnectCount.current < 5) { reconnectCount.current++; setTimeout(connect, 3000); }
    };
    ws.onerror = () => { ws.close(); };
  }, [url, playNextAudio]);

  const disconnect = useCallback(() => {
    reconnectCount.current = 99;
    if (wsRef.current) wsRef.current.close();
    setStatus('disconnected');
  }, []);

  const sendMessage = useCallback((type, data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }));
    }
  }, []);

  useEffect(() => {
    return () => { reconnectCount.current = 99; if (wsRef.current) wsRef.current.close(); };
  }, []);

  return { status, aiText, connect, disconnect, sendMessage, getAudioContext };
}
