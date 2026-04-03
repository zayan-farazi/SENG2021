import { useEffect, useRef, useState } from "react";
import createGlobe, { type COBEOptions } from "cobe";
import { useMotionValue, useSpring } from "motion/react";

const MOVEMENT_DAMPING = 1400;
const VIEWBOX_SIZE = 1000;
const SPHERE_RADIUS = 285;

type MarkerSeed = {
  id: string;
  location: [number, number];
  size: number;
  color: [number, number, number];
};

const MARKER_SEEDS: MarkerSeed[] = [
  { id: "london", location: [51.5074, -0.1278], size: 0.08, color: [0.50, 0.91, 1.0] },
  { id: "new-york", location: [40.7128, -74.006], size: 0.1, color: [0.70, 0.78, 1.0] },
  { id: "tokyo", location: [35.6762, 139.6503], size: 0.08, color: [0.44, 0.85, 1.0] },
  { id: "singapore", location: [1.3521, 103.8198], size: 0.065, color: [0.45, 0.97, 0.82] },
  { id: "sydney", location: [-33.8688, 151.2093], size: 0.07, color: [0.60, 0.80, 1.0] },
  { id: "paris", location: [48.8566, 2.3522], size: 0.07, color: [0.62, 0.86, 1.0] },
  { id: "dubai", location: [25.2048, 55.2708], size: 0.07, color: [0.58, 0.96, 0.87] },
  { id: "hong-kong", location: [22.3193, 114.1694], size: 0.08, color: [0.46, 0.90, 1.0] },
  { id: "sao-paulo", location: [-23.5505, -46.6333], size: 0.065, color: [0.73, 0.83, 1.0] },
  { id: "mumbai", location: [19.076, 72.8777], size: 0.075, color: [0.52, 0.94, 0.86] },
  { id: "beijing", location: [39.9042, 116.4074], size: 0.085, color: [0.45, 0.84, 1.0] },
  { id: "moscow", location: [55.7558, 37.6173], size: 0.06, color: [0.70, 0.79, 1.0] },
  { id: "los-angeles", location: [34.0522, -118.2437], size: 0.07, color: [0.66, 0.88, 1.0] },
  { id: "toronto", location: [43.6532, -79.3832], size: 0.065, color: [0.68, 0.84, 1.0] },
  { id: "mexico-city", location: [19.4326, -99.1332], size: 0.06, color: [0.62, 0.86, 1.0] },
  { id: "berlin", location: [52.52, 13.405], size: 0.06, color: [0.72, 0.84, 1.0] },
  { id: "cairo", location: [30.0444, 31.2357], size: 0.058, color: [0.55, 0.95, 0.86] },
  { id: "johannesburg", location: [-26.2041, 28.0473], size: 0.06, color: [0.55, 0.87, 1.0] },
  { id: "seoul", location: [37.5665, 126.978], size: 0.07, color: [0.46, 0.88, 1.0] },
  { id: "bangkok", location: [13.7563, 100.5018], size: 0.058, color: [0.45, 0.96, 0.84] },
  { id: "san-francisco", location: [37.7749, -122.4194], size: 0.065, color: [0.68, 0.88, 1.0] },
  { id: "buenos-aires", location: [-34.6037, -58.3816], size: 0.058, color: [0.66, 0.82, 1.0] },
  { id: "auckland", location: [-36.8509, 174.7645], size: 0.055, color: [0.54, 0.86, 1.0] },
  { id: "madrid", location: [40.4168, -3.7038], size: 0.058, color: [0.72, 0.84, 1.0] },
];

const GLOBE_CONFIG: COBEOptions = {
  width: 800,
  height: 800,
  onRender: () => {},
  devicePixelRatio: 2,
  phi: 0,
  theta: 0.3,
  dark: 1,
  diffuse: 3,
  mapSamples: 16000,
  mapBrightness: 6,
  baseColor: [0.14, 0.15, 0.18],
  markerColor: [0.23, 0.75, 0.63],
  glowColor: [0.1, 0.11, 0.14],
  markers: MARKER_SEEDS.map(marker => ({
    location: marker.location,
    size: marker.size,
    color: marker.color,
  })),
};

type PulseMarker = {
  id: string;
  x: number;
  y: number;
  size: number;
  color: string;
  glow: string;
  opacity: number;
};

function rgbTripletToString(rgb: [number, number, number]) {
  return `rgb(${Math.round(rgb[0] * 255)} ${Math.round(rgb[1] * 255)} ${Math.round(rgb[2] * 255)})`;
}

function rgbaTripletToString(rgb: [number, number, number], alpha: number) {
  return `rgba(${Math.round(rgb[0] * 255)}, ${Math.round(rgb[1] * 255)}, ${Math.round(rgb[2] * 255)}, ${alpha})`;
}

function buildVisiblePulseMarkers(phi: number, theta: number): PulseMarker[] {
  const thetaRad = theta;
  const cosTheta = Math.cos(thetaRad);
  const sinTheta = Math.sin(thetaRad);

  return MARKER_SEEDS.flatMap(marker => {
    const [latDeg, lonDeg] = marker.location;
    const lat = (latDeg * Math.PI) / 180;
    const lon = (lonDeg * Math.PI) / 180;

    const x = Math.cos(lat) * Math.sin(lon);
    const y = Math.sin(lat);
    const z = Math.cos(lat) * Math.cos(lon);

    const rotatedX = x * Math.cos(phi) - z * Math.sin(phi);
    const rotatedZ = x * Math.sin(phi) + z * Math.cos(phi);
    const tiltedY = y * cosTheta - rotatedZ * sinTheta;
    const tiltedZ = y * sinTheta + rotatedZ * cosTheta;

    if (tiltedZ < 0.18) {
      return [];
    }

    const brightness = Math.min(1, Math.max(0.35, tiltedZ));
    return [
      {
        id: marker.id,
        x: VIEWBOX_SIZE / 2 + rotatedX * SPHERE_RADIUS,
        y: VIEWBOX_SIZE / 2 - tiltedY * SPHERE_RADIUS,
        size: 10 + marker.size * 34,
        color: rgbTripletToString(marker.color),
        glow: rgbaTripletToString(marker.color, 0.34),
        opacity: brightness,
      },
    ];
  });
}

export function Globe() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<number | null>(null);
  const pointerInteractionMovement = useRef(0);
  const [failed, setFailed] = useState(false);
  const [pulseMarkers, setPulseMarkers] = useState<PulseMarker[]>([]);
  const rotation = useMotionValue(0);
  const smoothRotation = useSpring(rotation, {
    mass: 1,
    damping: 30,
    stiffness: 100,
  });

  const updatePointerInteraction = (value: number | null) => {
    pointerInteracting.current = value;
    if (canvasRef.current) {
      canvasRef.current.style.cursor = value === null ? "grab" : "grabbing";
    }
  };

  const updateMovement = (clientX: number) => {
    if (pointerInteracting.current === null) {
      return;
    }

    const delta = clientX - pointerInteracting.current;
    pointerInteractionMovement.current = delta;
    rotation.set(rotation.get() + delta / MOVEMENT_DAMPING);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof window === "undefined") {
      return;
    }

    let phi = 0;
    let width = 0;
    let fadeTimer: ReturnType<typeof window.setTimeout> | null = null;
    let lastMarkerSync = 0;

    const onResize = () => {
      width = canvas.offsetWidth;
    };

    window.addEventListener("resize", onResize);
    onResize();

    if (!width) {
      setFailed(true);
      window.removeEventListener("resize", onResize);
      return;
    }

    try {
      const globe = createGlobe(canvas, {
        ...GLOBE_CONFIG,
        width: width * 2,
        height: width * 2,
        onRender: state => {
          if (!pointerInteracting.current) {
            phi += 0.005;
          }

          const currentRotation = phi + smoothRotation.get();
          state.phi = currentRotation;
          state.width = width * 2;
          state.height = width * 2;
          const now = performance.now();
          if (now - lastMarkerSync > 48) {
            lastMarkerSync = now;
            setPulseMarkers(buildVisiblePulseMarkers(currentRotation, state.theta ?? GLOBE_CONFIG.theta));
          }
        },
      });

      fadeTimer = window.setTimeout(() => {
        canvas.style.opacity = "1";
      }, 0);

      setFailed(false);

      return () => {
        if (fadeTimer !== null) {
          window.clearTimeout(fadeTimer);
        }
        globe.destroy();
        window.removeEventListener("resize", onResize);
      };
    } catch {
      if (fadeTimer !== null) {
        window.clearTimeout(fadeTimer);
      }
      setFailed(true);
      window.removeEventListener("resize", onResize);
    }
  }, [smoothRotation]);

  if (failed) {
    return <div className="landing-globe-fallback" aria-hidden="true" />;
  }

  return (
    <div className="landing-globe-panel" aria-hidden="true">
      <div className="landing-globe-frame">
        <div className="landing-globe-glow" />
        <svg className="landing-globe-pulses" viewBox="0 0 1000 1000" aria-hidden="true">
          {pulseMarkers.map(marker => (
            <g key={marker.id} style={{ opacity: marker.opacity }}>
              <circle
                className="landing-globe-pulse-glow"
                cx={marker.x}
                cy={marker.y}
                r={marker.size}
                style={{ fill: marker.glow }}
              />
              <circle
                className="landing-globe-pulse-core"
                cx={marker.x}
                cy={marker.y}
                r={Math.max(2.4, marker.size * 0.22)}
                style={{ fill: marker.color }}
              />
            </g>
          ))}
        </svg>
        <canvas
          ref={canvasRef}
          className="landing-globe-canvas"
          onPointerDown={event => updatePointerInteraction(event.clientX)}
          onPointerUp={() => updatePointerInteraction(null)}
          onPointerOut={() => updatePointerInteraction(null)}
          onMouseMove={event => updateMovement(event.clientX)}
          onTouchMove={event => {
            if (event.touches[0]) {
              updateMovement(event.touches[0].clientX);
            }
          }}
        />
      </div>
    </div>
  );
}
