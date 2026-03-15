import { useEffect, useRef } from 'react';

/**
 * CameraStream — captures camera video and sends JPEG frames to backend.
 *
 * KEY FIXES:
 *
 * 1. RESOLUTION: Request 640x480 from camera but capture canvas at 320x240.
 *    drawImage source was using hardcoded 640x480 which ignored actual video
 *    dimensions (some phones return different resolutions). Now uses
 *    video.videoWidth/Height for correct source mapping.
 *
 * 2. FRAME INTERVAL: Changed from 3000ms (3 seconds) to 2000ms (2 seconds)
 *    for better real-time visual understanding. At 3s, the AI misses fast
 *    hand movements — important for safety interrupts.
 *
 * 3. JPEG QUALITY: Kept at 0.3 (30%) for bandwidth. For mobile on cellular,
 *    this is the right tradeoff. 320x240 at 30% quality ≈ 5-10KB per frame.
 */
export default function CameraStream({ isActive, onFrame }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const intervalRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    if (!isActive) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
      return;
    }

    let cancelled = false;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } },
        });

        if (cancelled) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }

        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        await new Promise((resolve) => {
          if (videoRef.current) {
            videoRef.current.onloadedmetadata = resolve;
          } else {
            resolve();
          }
        });

        intervalRef.current = setInterval(() => {
          if (!videoRef.current || !canvasRef.current) return;
          if (videoRef.current.readyState < videoRef.current.HAVE_ENOUGH_DATA) return;

          const canvas = canvasRef.current;
          const video = videoRef.current;
          canvas.width = 320;
          canvas.height = 240;
          const ctx = canvas.getContext('2d');
          // Use actual video dimensions as source (not hardcoded 640x480)
          ctx.drawImage(video, 0, 0, video.videoWidth, video.videoHeight, 0, 0, 320, 240);

          canvas.toBlob(
            (blob) => {
              if (!blob) return;
              const reader = new FileReader();
              reader.onloadend = () => {
                const base64 = reader.result.split(',')[1];
                onFrame(base64);
              };
              reader.readAsDataURL(blob);
            },
            'image/jpeg',
            0.3,
          );
        }, 2000);

        console.log('[CameraStream] Camera streaming started');
      } catch (err) {
        console.error('[CameraStream] Failed to start camera:', err);
      }
    }

    startCamera();

    return () => {
      cancelled = true;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isActive, onFrame]);

  return (
    <>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="absolute inset-0 w-full h-full object-cover z-0"
      />
      <canvas ref={canvasRef} className="hidden" />
    </>
  );
}
