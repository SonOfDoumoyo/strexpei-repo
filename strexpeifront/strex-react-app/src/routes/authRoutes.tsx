import { useState, useEffect } from "react";
import api from "../api";
import axios from "axios";
import { getUser } from "../context/userContext";
import type { User } from "../schemas/authTypes";
import { useUser } from "../context/userContext";

export function getUserFunc () {

    const {currentUser, setCurrentUser} = useUser();
    const [error, setError] = useState('');
    const user_id = getUser()?.user_id;
    

    useEffect(() => {
        let cancelled = false;
        
        async function fetchUser() {
            try{
                const response = await api.get("/auths/current_user");
                if (!cancelled) {const user = await response.data; setCurrentUser(user);}
            } catch (err: unknown) {
                if (cancelled) return;
                if (axios.isAxiosError(err)) {
                    setError(err.response?.data.detail || "Failed to fetch user"); 
                } else {
                    setError("Server not reachable");
                }
            }
        }

        fetchUser();

        return () => {
            cancelled = true;
        };

    }, []);

    return { currentUser, error }
}