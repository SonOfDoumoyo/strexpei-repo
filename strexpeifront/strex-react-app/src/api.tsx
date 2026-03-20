import axios, { type InternalAxiosRequestConfig } from "axios";
import { getAccessToken, setAccessToken, clearAccessToken } from "./hooks/useAuths";

const api = axios.create({
    baseURL: "http://localhost:8000/api/v1.0",
    withCredentials: true, //sends refresh token
});

//Attach access token automatically
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token) {
        config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
});


//Handle 401 -> refresh ->retry
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        
        if (error.response?.status === 400) {
            return Promise.reject(error);
        }

        if (
            originalRequest?._retry ||
            originalRequest?.url?.includes("/auths/logout") ||
            originalRequest?.url?.includes("/auths/refresh_access")) {
            clearAccessToken();
            return Promise.reject(error);
        }

        

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                const refreshRes = await api.get(
                    "/auths/refresh_access",
                    {...( { skipAuth: true } as any )},
                );

                const newToken = refreshRes.data.access_token;
                setAccessToken(newToken);

                api.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
                originalRequest.headers = originalRequest.headers ?? {};
                
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                return api(originalRequest);
                console.log(originalRequest);
            } catch (refreshError) {
                clearAccessToken();
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);

export default api;