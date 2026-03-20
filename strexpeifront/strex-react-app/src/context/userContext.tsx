import type { User } from "../schemas/authTypes";
import { useState, useCallback, createContext, useContext } from "react";

let loginUser: { user_id: string; user_email: string} | null = null;

export function setUser(user: { user_id: string; user_email: string }) {
    loginUser = user;
}

export function getUser() {
    return loginUser;
}

export function charUser() {
    loginUser = null;
}

type UserContextType = {
    currentUser: User | null;
    setCurrentUser: (user: User | null) => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
    const [currentUser, setCurrentUser] = useState<User | null>(null);

    return (
        <UserContext.Provider value={{ currentUser, setCurrentUser }}>
            {children}
        </UserContext.Provider>
    );
}

export function useUser() {
    const context = useContext(UserContext);
    if (!context) throw new Error("useUser must be used inside UserProvider");
    return context;
}