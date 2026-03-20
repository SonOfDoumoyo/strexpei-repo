import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx';
import "@fontsource/poppins/600.css";
import "@fontsource/roboto-slab/600.css";
import "@fontsource/sn-pro/600.css";
import "@fontsource/poppins/700.css";
import "@fontsource/poppins/400.css";
import "@fontsource/archivo-black/400.css"
import { UserProvider } from './context/userContext.tsx';
import ErrorBoundary from './utils/ErrorBoundary.tsx';

createRoot(document.getElementById('root')!).render(

    <UserProvider>
        <ErrorBoundary
            fallback={<h1>Oop! Something went wrong</h1>}
        >
       <App />
       </ErrorBoundary>
    </UserProvider>,
)
