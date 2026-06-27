import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import {
  PlayerProvider,
  cn,
  IconCat,
  IconFilm,
  IconGrid,
  IconBook,
  IconWand,
  IconCalendar,
  IconSun,
  IconMoon,
  IconGithub,
} from "./ui";
import { Gallery } from "./sections/Gallery";
import { Library } from "./sections/Library";
import { Stories } from "./sections/Stories";
import { Match } from "./sections/Match";
import { Calendar } from "./sections/Calendar";

type Tab = "gallery" | "calendar" | "library" | "stories" | "match";

const NAV: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "gallery", label: "Gallery", icon: <IconFilm className="w-4 h-4" /> },
  { id: "calendar", label: "Calendar", icon: <IconCalendar className="w-4 h-4" /> },
  { id: "library", label: "Library", icon: <IconGrid className="w-4 h-4" /> },
  { id: "stories", label: "Stories", icon: <IconBook className="w-4 h-4" /> },
  { id: "match", label: "Match", icon: <IconWand className="w-4 h-4" /> },
];

function useTheme() {
  const [dark, setDark] = useState(
    () => localStorage.getItem("crs-theme") !== "light",
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.classList.toggle("light", !dark);
    localStorage.setItem("crs-theme", dark ? "dark" : "light");
  }, [dark]);
  return { dark, toggle: () => setDark((d) => !d) };
}

const TAB_IDS = NAV.map((n) => n.id);
function tabFromHash(): Tab {
  const h = window.location.hash.replace("#", "") as Tab;
  return TAB_IDS.includes(h) ? h : "gallery";
}

export default function App() {
  const [tab, setTabState] = useState<Tab>(tabFromHash);
  const { dark, toggle } = useTheme();

  const setTab = (t: Tab) => {
    window.location.hash = t;
    setTabState(t);
  };

  useEffect(() => {
    const onHash = () => setTabState(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <PlayerProvider>
      <div className="min-h-full flex flex-col">
        {/* header */}
        <header className="sticky top-0 z-40 border-b border-black/5 dark:border-white/10 bg-white/60 dark:bg-ink/60 backdrop-blur-xl">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 h-16 flex items-center gap-3">
            <div className="flex items-center gap-2.5 mr-2">
              <div className="grid place-items-center w-9 h-9 rounded-xl bg-brand text-black shadow-[0_0_24px_-4px_rgba(194,255,77,0.7)]">
                <IconCat className="w-5 h-5" />
              </div>
              <div className="leading-none">
                <div className="font-display font-bold text-[15px] tracking-tight text-zinc-900 dark:text-white">
                  Cat Reel Studio
                </div>
                <div className="text-[11px] text-zinc-500 dark:text-zinc-400">
                  green-screen → POV reels
                </div>
              </div>
            </div>

            <nav className="hidden sm:flex items-center gap-1 ml-2">
              {NAV.map((n) => (
                <button
                  key={n.id}
                  onClick={() => setTab(n.id)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    tab === n.id
                      ? "bg-brand/15 text-zinc-900 dark:text-white"
                      : "text-zinc-500 dark:text-zinc-400 hover:bg-black/5 dark:hover:bg-white/5",
                  )}
                >
                  <span className={tab === n.id ? "text-brand" : ""}>{n.icon}</span>
                  {n.label}
                </button>
              ))}
            </nav>

            <div className="ml-auto flex items-center gap-1.5">
              <a
                href="https://github.com/Lulzx/catmeme-reel-engine"
                target="_blank"
                rel="noreferrer"
                className="grid place-items-center w-9 h-9 rounded-lg text-zinc-500 dark:text-zinc-400 hover:bg-black/5 dark:hover:bg-white/5 transition"
                aria-label="GitHub"
              >
                <IconGithub className="w-5 h-5" />
              </a>
              <button
                onClick={toggle}
                className="grid place-items-center w-9 h-9 rounded-lg text-zinc-500 dark:text-zinc-400 hover:bg-black/5 dark:hover:bg-white/5 transition"
                aria-label="Toggle theme"
              >
                {dark ? <IconSun className="w-5 h-5" /> : <IconMoon className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {/* mobile nav */}
          <div className="sm:hidden flex items-center gap-1 px-3 pb-2 overflow-x-auto">
            {NAV.map((n) => (
              <Button
                key={n.id}
                size="sm"
                variant={tab === n.id ? "primary" : "ghost"}
                onPress={() => setTab(n.id)}
              >
                {n.label}
              </Button>
            ))}
          </div>
        </header>

        <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 py-8">
          {tab === "gallery" && <Gallery onAuthor={() => setTab("stories")} />}
          {tab === "calendar" && <Calendar />}
          {tab === "library" && <Library />}
          {tab === "stories" && <Stories />}
          {tab === "match" && <Match />}
        </main>

        <footer className="border-t border-black/5 dark:border-white/10 py-6 text-center text-xs text-zinc-400 dark:text-zinc-500">
          Cat-Meme Reel Engine · catalog → match → render · built with HeroUI
        </footer>
      </div>
    </PlayerProvider>
  );
}
