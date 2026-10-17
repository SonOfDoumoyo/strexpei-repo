import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, refreshSession, setAccessToken, setSessionLostHandler } from "../lib/api";
import type { User } from "../lib/types";

type Status = "loading" | "authenticated" | "anonymous";
type SessionPayload = { access_token: string; user: User };

type Ctx = {
  user: User | null;
  status: Status;
  startSession: (payload: SessionPayload) => void;
  login: (email: string, password: string, remember: boolean) => Promise<User>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<void>;
  setUser: (user: User) => void;
};

const AuthContext = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const queryClient = useQueryClient();

  const startSession = useCallback((payload: SessionPayload) => {
    setAccessToken(payload.access_token);
    setUser(payload.user);
    setStatus("authenticated");
  }, []);

  const endSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    let alive = true;
    refreshSession()
      .then((result) => {
        if (!alive) return;
        if (result) startSession(result);
        else setStatus("anonymous");
      })
      .catch(() => alive && setStatus("anonymous"));
    setSessionLostHandler(() => endSession());
    return () => {
      alive = false;
      setSessionLostHandler(null);
    };
  }, [startSession, endSession]);

  const login = useCallback(
    async (email: string, password: string, remember: boolean) => {
      const payload = await api.post<SessionPayload>("/auth/login", { email: email.trim(), password, remember_me: remember });
      startSession(payload);
      return payload.user;
    },
    [startSession],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* the local session is cleared regardless */
    }
    endSession();
  }, [endSession]);

  const reloadUser = useCallback(async () => {
    const me = await api.get<User>("/auth/me");
    setUser(me);
  }, []);

  const value = useMemo<Ctx>(() => ({ user, status, startSession, login, logout, reloadUser, setUser }), [user, status, startSession, login, logout, reloadUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
