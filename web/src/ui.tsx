import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Chip } from "@heroui/react";
import type { Clip } from "./api";

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/* ----------------------------------------------------------------- icons -- */
type IP = { className?: string };
const S = (p: { children: ReactNode } & IP) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={p.className}
  >
    {p.children}
  </svg>
);
export const IconPlay = (p: IP) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={p.className}>
    <path d="M8 5.14v13.72a1 1 0 0 0 1.53.85l10.5-6.86a1 1 0 0 0 0-1.7L9.53 4.29A1 1 0 0 0 8 5.14Z" />
  </svg>
);
export const IconSearch = (p: IP) => (
  <S {...p}><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></S>
);
export const IconSun = (p: IP) => (
  <S {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></S>
);
export const IconMoon = (p: IP) => (
  <S {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" /></S>
);
export const IconFilm = (p: IP) => (
  <S {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4" /></S>
);
export const IconGrid = (p: IP) => (
  <S {...p}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></S>
);
export const IconBook = (p: IP) => (
  <S {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14Z" /><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5" /></S>
);
export const IconWand = (p: IP) => (
  <S {...p}><path d="M15 4V2M15 10V8M9 4H7M19 4h-2M12.5 6.5 11 5M18 11l-1.5-1.5M4 20l9-9M14 7l3 3" /></S>
);
export const IconClose = (p: IP) => (
  <S {...p}><path d="M18 6 6 18M6 6l12 12" /></S>
);
export const IconBolt = (p: IP) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={p.className}>
    <path d="M13 2 4.5 13.5a.6.6 0 0 0 .5.95H11l-1 7.5a.5.5 0 0 0 .9.37L19.5 11a.6.6 0 0 0-.5-.95H13l1-7.7a.5.5 0 0 0-.9-.35Z" />
  </svg>
);
export const IconGithub = (p: IP) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={p.className}>
    <path d="M12 2A10 10 0 0 0 8.8 21.5c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.3-3.4-1.3-.4-1.2-1.1-1.5-1.1-1.5-.9-.6 0-.6 0-.6 1 .1 1.6 1 1.6 1 .9 1.6 2.4 1.1 3 .9 0-.7.3-1.1.6-1.4-2.2-.300-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7 0-.3-.4-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .3.3.6.9.6 1.8v2.7c0 .3.2.6.7.5A10 10 0 0 0 12 2Z" />
  </svg>
);
export const IconCat = (p: IP) => (
  <S {...p}><path d="M4 4.5 7 8a8 8 0 0 1 10 0l3-3.5V14a8 8 0 0 1-16 0V4.5Z" /><path d="M9.5 12h.01M14.5 12h.01M12 15c.8 0 1.3-.4 1.3-.4M10.7 14.6s.5.4 1.3.4" /></S>
);

export const IconCalendar = (p: IP) => (
  <S {...p}><rect x="3" y="4.5" width="18" height="16" rx="2" /><path d="M3 9h18M8 3v3M16 3v3" /></S>
);
export const IconClock = (p: IP) => (
  <S {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></S>
);
export const IconChevronLeft = (p: IP) => (
  <S {...p}><path d="m14 6-6 6 6 6" /></S>
);
export const IconChevronRight = (p: IP) => (
  <S {...p}><path d="m10 6 6 6-6 6" /></S>
);
export const IconCheck = (p: IP) => (
  <S {...p}><path d="m5 12 4.5 4.5L19 7" /></S>
);
export const IconYoutube = (p: IP) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={p.className}>
    <path d="M21.6 7.2a2.5 2.5 0 0 0-1.7-1.8C18.2 5 12 5 12 5s-6.2 0-7.9.4A2.5 2.5 0 0 0 2.4 7.2 26 26 0 0 0 2 12a26 26 0 0 0 .4 4.8 2.5 2.5 0 0 0 1.7 1.8C5.8 19 12 19 12 19s6.2 0 7.9-.4a2.5 2.5 0 0 0 1.7-1.8A26 26 0 0 0 22 12a26 26 0 0 0-.4-4.8ZM10 15V9l5 3-5 3Z" />
  </svg>
);
export const IconExternal = (p: IP) => (
  <S {...p}><path d="M14 5h5v5M19 5l-8 8M19 13v6H5V5h6" /></S>
);

/* ----------------------------------------------------------- quality chip -- */
const QMAP: Record<Clip["quality"], { color: "success" | "warning" | "danger" | "accent" | "default"; label: string }> = {
  good: { color: "success", label: "good" },
  ok: { color: "accent", label: "ok" },
  partial: { color: "warning", label: "partial" },
  low: { color: "warning", label: "low-res" },
  avoid: { color: "danger", label: "avoid" },
};
export function QualityChip({ quality, size = "sm" }: { quality: Clip["quality"]; size?: "sm" | "md" }) {
  const q = QMAP[quality] ?? QMAP.ok;
  return (
    <Chip color={q.color} variant="soft" size={size}>
      {q.label}
    </Chip>
  );
}

/* ---------------------------------------------------------- video player -- */
type PlayItem = { src: string; title: string; subtitle?: string; portrait?: boolean };
const PlayerCtx = createContext<(i: PlayItem) => void>(() => {});
export const usePlayer = () => useContext(PlayerCtx);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const [item, setItem] = useState<PlayItem | null>(null);
  const play = useCallback((i: PlayItem) => setItem(i), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setItem(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <PlayerCtx.Provider value={play}>
      {children}
      <AnimatePresence>
        {item && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setItem(null)}
          >
            <motion.div
              className="relative flex flex-col items-center gap-3"
              initial={{ scale: 0.9, y: 16 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.92, opacity: 0 }}
              transition={{ type: "spring", stiffness: 320, damping: 28 }}
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setItem(null)}
                className="absolute -top-3 -right-3 z-10 grid place-items-center w-9 h-9 rounded-full bg-white text-black shadow-lg hover:scale-105 transition"
                aria-label="Close"
              >
                <IconClose className="w-5 h-5" />
              </button>
              <video
                key={item.src}
                src={item.src}
                controls
                autoPlay
                playsInline
                className={cn(
                  "rounded-2xl shadow-2xl bg-black ring-1 ring-white/10",
                  item.portrait
                    ? "max-h-[82vh] max-w-[min(94vw,46vh)]"
                    : "max-h-[78vh] max-w-[92vw]",
                )}
              />
              <div className="text-center">
                <p className="font-display font-semibold text-white">{item.title}</p>
                {item.subtitle && (
                  <p className="text-sm text-white/55">{item.subtitle}</p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </PlayerCtx.Provider>
  );
}

/* ------------------------------------------------------------ misc bits --- */
export function Pill({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium",
        "bg-black/5 dark:bg-white/8 text-zinc-600 dark:text-zinc-300",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function SectionTitle({ title, sub, icon }: { title: string; sub?: string; icon?: ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      {icon && (
        <div className="grid place-items-center w-10 h-10 rounded-xl bg-brand/15 text-brand">
          {icon}
        </div>
      )}
      <div>
        <h2 className="font-display text-2xl font-700 font-semibold tracking-tight text-zinc-900 dark:text-white">
          {title}
        </h2>
        {sub && <p className="text-sm text-zinc-500 dark:text-zinc-400">{sub}</p>}
      </div>
    </div>
  );
}
