import { getUserFunc } from "../routes/authRoutes"; 

export function useUserPage () {
    const { currentUser, error } = getUserFunc();

    return {
        currentUser: currentUser ?? null,
        error,
        loading: !error && !currentUser,
    };
}