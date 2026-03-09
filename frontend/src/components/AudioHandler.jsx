import { useEffect, useRef } from 'react';

export default function AudioHandler({ isActive, onAudioChunk }) {
  const streamRef = useRef(null);
  const processorRef = useRef(null);
  const contextRef = useRef(null);
  const isActiveRef = useRef(isActive);

  useEffect(() => {
    isActiveRef.current = isActive;
  }, [isActive]);

  useEffect(() => {
    if (!isActive) {
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      if (contextRef.current && contextRef.current.state !== 'closed') {
        contextRef.current.close().catch(() => {});
        contextRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
      return;
    }

    let cancelled = false;

    async function startAudio() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        if (cancelled) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }

        streamRef.current = stream;
        const audioContext = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: 16000,
        });
        contextRef.current = audioContext;

        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
          if (!isActiveRef.current) return;
          const inputData = e.inputBuffer.getChannelData(0);

          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += Math.abs(inputData[i]);
          }
          const avg = sum / inputData.length;
          if (avg < 0.001) return;

          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
          }
          const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
          onAudioChunk(base64);
        };

        source.connect(processor);
        processor.connect(audioContext.destination);
        console.log('[AudioHandler] Microphone streaming started');
      } catch (err) {
        console.error('[AudioHandler] Failed to start audio:', err);
      }
    }

    startAudio();

    return () => {
      cancelled = true;
    };
  }, [isActive, onAudioChunk]);

  return null;
}
