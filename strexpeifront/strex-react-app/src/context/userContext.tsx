import type { User } from "../schemas/authTypes";
import React, { useState, createContext, useContext, useEffect, useCallback } from "react";
import axios from "axios";
import api from "../api";
import "../assets/css/layout.css";
import { useLocation } from "react-router-dom";
import { getCurrentUid } from "../hooks/currentUid";
import { clearAccessToken } from "../hooks/useAuths";

type UserContextType = {
    currentUser: User | null;
    setCurrentUser: React.Dispatch<React.SetStateAction<User | null>>;
    fetchUser: () => Promise<void>;
    loading: boolean;
}

export const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
    const [error, setError] = useState("");
    const [currentUser, setCurrentUser] = useState<User | null>(null);
    const [ loading, setLoading ] = useState(true);
    const location = useLocation();
    const authRoutes = ["/sign-in", "/sign-up", "/verify-account"]
    const isAuthPage = authRoutes.includes(location.pathname)
    

    const fetchUser = useCallback(async () => {
        const uid = getCurrentUid();
        if (!uid) {
            setLoading(false);
            return;
        }
        try{
            setLoading(true)
            const response = await api.get("/auths/current_user");
            setCurrentUser(response.data);
        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                if (err.response?.status === 403) {
                    setCurrentUser(null);
                    clearAccessToken(uid);
                }
                setError(err.response?.data.detail || "Failed to fetch user"); 
            } else {
                setError("Server not reachable");
            }
        } finally {
            setLoading(false);
        }
    }, []);
        
    useEffect(() => {
        if (isAuthPage) { 
            setLoading(false);
            return
        };
        if (currentUser) {
            setLoading(false); 
            return;
        }
        fetchUser();
    }, [isAuthPage])
    // console.log(currentUser)

    return (
        <UserContext.Provider value={{ currentUser, setCurrentUser, fetchUser, loading}}>
            <div className="loading-container">
                {loading && !isAuthPage ? <div className="loading"><div className="fi-loading"></div></div>:children}
            </div>
        </UserContext.Provider>
    );
}

export function useUser() {
    const context = useContext(UserContext);
    if (!context) throw new Error("useUser must be used inside UserProvider");
    return context;
}