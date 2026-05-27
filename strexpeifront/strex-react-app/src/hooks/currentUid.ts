import api from "../api";
import { getAccessToken } from "./useAuths";

export const setCurrentUid = (uid: string) => {
    const existing =getActiveUids();
    if (!existing.includes(uid)) {
        existing.push(uid);
    }
    sessionStorage.setItem("active_uids", JSON.stringify(existing));
    sessionStorage.setItem("current_uid", uid)
}

export const getActiveUids = (): string[] => {
    const raw = sessionStorage.getItem("active_uids");
    return raw ? JSON.parse(raw) : [];
}


export const getCurrentUid = (): string | null => {
    return sessionStorage.getItem("current_uid")
}

export const switchUser = (uid: string) => {
    const active = getActiveUids();
    if (active.includes(uid)) {
        sessionStorage.setItem("current_uid", uid);
        const token = getAccessToken(uid);

        if (token) {
            api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
        }
    }
}

export const clearUid = (uid: string) => {
    const remaining = getActiveUids().filter(id => id !== uid);
    sessionStorage.setItem("active_uids", JSON.stringify(remaining));

    if (getCurrentUid() === uid) {
        const next = remaining[0] ?? null;
        if (next) {
            sessionStorage.setItem("current_uid", next);
        } else {
            sessionStorage.removeItem("current_uid");
        }
    } 
}