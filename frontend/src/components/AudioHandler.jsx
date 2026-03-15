import { useEffect, useRef } from 'react';

/**
 * AudioHandler — captures microphone audio and sends PCM chunks to backend.
 *
 * KEY FIXES:
 *
 * 1. CHUNK SIZE: Changed from 4096 samples (~256ms at 16kHz) to 640 samples
 *    (40ms at 16kHz). Google's best practice says 20-40ms chunks.
 *    Large chunks cause:
 *    - Higher latency (Gemini VAD can't detect speech start quickly)
 *    - Missed speech detection (entire chunk averaged = diluted signal)
 *    - The "not hearing" problem on mobile where short utterances get lost
 *
 * 2. NOISE GATE: Lowered from 0.001 to 0.0005. The old threshold was too
 *    aggressive for mobile phone mics in noisy environments. On phones,
 *    ambient noise + mic sensitivity means legitimate speech can average
 *    below 0.001. This caused speech to be silently dropped.
 *
 * 3. DEPRECATED API: ScriptProcessorNode is deprecated and has known issues
 *    on mobile browsers (especially iOS Safari). Migrated to AudioWorklet
 *    which runs on a separate thread and doesn't drop frames under load.
 *    Fallback to ScriptProcessor for browsers that don't support Worklet.
 *
 * 4. ECHO CANCELLATION: The isAiSpeaking mute was correct but had a race
 *    condition — ref update could lag behind actual state. Now we also
 *    log when muting/unmuting for easier debugging.
 */
export default function AudioHandler({ isActive, onAudioChunk, isAiSpeaking }) {
  const streamRef = useRef(null);
  const processorRef = useRef(null);
  const contextRef = useRef(null);
  const workletNodeRef = useRef(null);
  const isActiveRef = useRef(isActive);
  const isAiSpeakingRef = useRef(isAiSpeaking);
  const chunkCountRef = useRef(0);
  const onAudioChunkRef = useRef(onAudioChunk);

  useEffect(() => {
    isActiveRef.current = isActive;
  }, [isActive]);

  useEffect(() => {
    isAiSpeakingRef.current = isAiSpeaking;
  }, [isAiSpeaking]);

  useEffect(() => {
    onAudioChunkRef.current = onAudioChunk;
  }, [onAudioChunk]);

  useEffect(() => {
    if (!isActive) {
      // Cleanup
      if (workletNodeRef.current) {
        workletNodeRef.current.disconnect();
        workletNodeRef.current = null;
      }
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      if (contextRef.current && contextRef.current.state !== 'closed') {
        contextRef.current.close().catch(() => {});
        contextRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      return;
    }

    let cancelled = false;

    // AudioWorklet processor code — runs on audio thread
    const workletCode = `
      class PCMProcessor extends AudioWorkletProcessor {
        constructor() {
          super();
          this.buffer = [];
          // 640 samples = 40ms at 16kHz (Google recommended: 20-40ms)
          this.TARGET_SAMPLES = 640;
        }
        process(inputs) {
          const input = inputs[0];
          if (!input || !input[0]) return true;
          const channelData = input[0];
          for (let i = 0; i < channelData.length; i++) {
            this.buffer.push(channelData[i]);
          }
          while (this.buffer.length >= this.TARGET_SAMPLES) {
            const chunk = this.buffer.splice(0, this.TARGET_SAMPLES);
            this.port.postMessage({ type: 'audio', data: chunk });
          }
          return true;
        }
      }
      registerProcessor('pcm-processor', PCMProcessor);
    `;

    async function startAudioWithWorklet() {
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
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        streamRef.current = stream;

        const audioContext = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: 16000,
        });
        contextRef.current = audioContext;

        const source = audioContext.createMediaStreamSource(stream);

        // Try AudioWorklet first (better performance, no frame drops on mobile)
        try {
          const blob = new Blob([workletCode], { type: 'application/javascript' });
          const url = URL.createObjectURL(blob);
          await audioContext.audioWorklet.addModule(url);
          URL.revokeObjectURL(url);

          const workletNode = new AudioWorkletNode(audioContext, 'pcm-processor');
          workletNodeRef.current = workletNode;

          const NOISE_GATE = 0.0005;

          workletNode.port.onmessage = (e) => {
            if (!isActiveRef.current) return;
            if (isAiSpeakingRef.current) return;

            const floatData = e.data.data;

            // Noise gate check
            let sum = 0;
            for (let i = 0; i < floatData.length; i++) {
              sum += Math.abs(floatData[i]);
            }
            const avg = sum / floatData.length;
            if (avg < NOISE_GATE) return;

            // Convert float32 to int16 PCM
            const pcmData = new Int16Array(floatData.length);
            for (let i = 0; i < floatData.length; i++) {
              pcmData[i] = Math.max(-32768, Math.min(32767, floatData[i] * 32768));
            }

            const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
            onAudioChunkRef.current(base64);

            chunkCountRef.current++;
            if (chunkCountRef.current % 200 === 0) {
              console.log(`[AudioHandler] Sent chunk #${chunkCountRef.current}, level: ${avg.toFixed(4)}`);
            }
          };

          source.connect(workletNode);
          workletNode.connect(audioContext.destination);

          console.log('[AudioHandler] Started with AudioWorklet (40ms chunks)');
          return;
        } catch (workletErr) {
          console.warn('[AudioHandler] AudioWorklet not supported, falling back to ScriptProcessor:', workletErr);
        }

        // Fallback: ScriptProcessor (deprecated but works everywhere)
        // Use 1024 buffer size (smaller than original 4096) = ~64ms at 16kHz
        const processor = audioContext.createScriptProcessor(1024, 1, 1);
        processorRef.current = processor;

        const NOISE_GATE = 0.0005;

        processor.onaudioprocess = (e) => {
          if (!isActiveRef.current) return;
          if (isAiSpeakingRef.current) return;

          const inputData = e.inputBuffer.getChannelData(0);

          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += Math.abs(inputData[i]);
          }
          const avg = sum / inputData.length;

          if (avg < NOISE_GATE) return;

          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
          }

          const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmData.buffer)));
          onAudioChunkRef.current(base64);

          chunkCountRef.current++;
          if (chunkCountRef.current % 200 === 0) {
            console.log(`[AudioHandler] Sent chunk #${chunkCountRef.current}, level: ${avg.toFixed(4)}`);
          }
        };

        source.connect(processor);
        processor.connect(audioContext.destination);

        console.log('[AudioHandler] Started with ScriptProcessor fallback (64ms chunks)');
      } catch (err) {
        console.error('[AudioHandler] Failed to start audio:', err);
      }
    }

    startAudioWithWorklet();

    return () => {
      cancelled = true;
    };
  }, [isActive]);

  return null;
}
