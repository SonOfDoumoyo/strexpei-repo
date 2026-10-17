import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "./auth";

export type Mode = "light" | "dark";
export type Accent = { id: string; name: string; light: string; strong: string; dark: string; soft: string; darkSoft: string; locked: boolean };

/** The base identity plus the subscriber accents from the original design. */
export const ACCENTS: Accent[] = [
  { id: "classic", name: "Streixpei", light: "#B8904A", strong: "#9A7536", dark: "#C4A15C", soft: "#F2E9DA", darkSoft: "rgba(196,161,92,.14)", locked: false },
  { id: "gold", name: "Gold", light: "#C6A15B", strong: "#A5823F", dark: "#D4B36F", soft: "#F3E7C8", darkSoft: "rgba(212,179,111,.15)", locked: true },
  { id: "diamond", name: "Diamond", light: "#8EA4B9", strong: "#6E8499", dark: "#A9BCCF", soft: "#E9EEF2", darkSoft: "rgba(169,188,207,.14)", locked: true },
  { id: "premium", name: "Premium", light: "#8B73D6", strong: "#6F58BD", dark: "#A592E6", soft: "#ECE8F7", darkSoft: "rgba(165,146,230,.16)", locked: true },
];

type Ctx = { mode: Mode; setMode: (m: Mode) => void; toggleMode: () => void; accent: Accent; setAccent: (id: string) => void; canCustomize: boolean };
const ThemeContext = createContext<Ctx | null>(null);

function readMode(): Mode {
  try {
    const saved = localStorage.getItem("spx.mode");
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* storage unavailable */
  }
  return document.documentElement.dataset.mode === "dark" ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [mode, setModeState] = useState<Mode>(readMode);
  const [accentId, setAccentId] = useState<string>(() => {
    try {
      return localStorage.getItem("spx.accent") ?? "classic";
    } catch {
      return "classic";
    }
  });
  const canCustomize = Boolean(user?.has_paid_plan);
  const accent = ACCENTS.find((a) => a.id === accentId && (!a.locked || canCustomize)) ?? ACCENTS[0];

  useEffect(() => {
    document.documentElement.dataset.mode = mode;
    document.querySelector('meta[name="theme-color"]:not([media])')?.setAttribute("content", mode === "dark" ? "#100E0B" : "#F7F3EC");
  }, [mode]);

  useEffect(() => {
    const root = document.documentElement.style;
    if (accent.id === "classic") {
      ["--c-brand", "--c-brand-strong", "--c-brand-soft", "--c-glow"].forEach((v) => root.removeProperty(v));
      return;
    }
    const dark = mode === "dark";
    root.setProperty("--c-brand", dark ? accent.dark : accent.light);
    root.setProperty("--c-brand-strong", dark ? accent.dark : accent.strong);
    root.setProperty("--c-brand-soft", dark ? accent.darkSoft : accent.soft);
    root.setProperty("--c-glow", `${dark ? accent.dark : accent.light}33`);
  }, [accent, mode]);

  const setMode = useCallback((m: Mode) => {
    setModeState(m);
    try {
      localStorage.setItem("spx.mode", m);
    } catch {
      /* ignore */
    }
  }, []);

  const setAccent = useCallback((id: string) => {
    setAccentId(id);
    try {
      localStorage.setItem("spx.accent", id);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<Ctx>(
    () => ({ mode, setMode, toggleMode: () => setMode(mode === "dark" ? "light" : "dark"), accent, setAccent, canCustomize }),
    [mode, setMode, accent, setAccent, canCustomize],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
