import axios, { type InternalAxiosRequestConfig } from "axios";
import { getAccessToken, setAccessToken, clearAccessToken } from "./hooks/useAuths";
import { getCurrentUid } from "./hooks/currentUid";


let isLoggingOut = false;

export const setLoggingOut = (val: boolean) => isLoggingOut = val;

const api = axios.create({
    baseURL: "http://localhost:8000/api/v1.0",
    withCredentials: true, //sends refresh token
});

//Attach access token automatically
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const uid = getCurrentUid();
    if (!uid) return config;
    const token = getAccessToken(uid);

    if (token) {
        config.headers["Authorization"] = `Bearer ${token}`;
    } else {
        delete config.headers["Authorization"];
    }
    return config;
});


//Handle 401 -> refresh ->retry
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        const uid = getCurrentUid()
        
        if (error.response?.status === 400) {
            return Promise.reject(error);
        }

        if (
            originalRequest?._retry ||
            originalRequest?.skipAuth ||
            originalRequest?.url?.includes("/auths/logout") ||
            originalRequest?.url?.includes("/auths/refresh_access")) {
            clearAccessToken(uid!);
            return Promise.reject(error);
        }

        if (isLoggingOut) return Promise.reject(error);

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                const refreshRes = await api.post(
                    `/auths/refresh_access?uid=${uid!}`,
                    {},
                    { withCredentials: true }
                );

                const newUid = refreshRes.data.user.user_id;
                const newToken = refreshRes.data.user.access_token;
                setAccessToken(newUid, newToken);

                
                api.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
                originalRequest.headers = originalRequest.headers ?? {};
                
                originalRequest.headers.Authorization = `Bearer ${newToken}`;

                return api(originalRequest);

            } catch (refreshError) {
                clearAccessToken(uid!);
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);



export default api;