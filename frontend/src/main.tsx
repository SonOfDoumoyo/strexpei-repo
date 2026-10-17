import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { AuthProvider } from "./context/auth";
import { ThemeProvider } from "./context/theme";
import { WorkgroupProvider } from "./context/workgroup";
import { ToastProvider } from "./components/toast";
import { ApiError } from "./lib/api";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: (count, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return count < 2;
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ThemeProvider>
            <WorkgroupProvider>
              <ToastProvider>
                <App />
              </ToastProvider>
            </WorkgroupProvider>
          </ThemeProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
