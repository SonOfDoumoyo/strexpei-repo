import { useEffect, useState} from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";
import NavBar from "./NavBar";
import "../assets/css/layout.css";
import "../assets/css/navbar.css";
import { useNavigate } from "react-router-dom";
import { useContext } from "react";
import { UserContext } from "../context/userContext";
import { Navigate } from "react-router-dom";
import { setCurrentUid } from "../hooks/currentUid";


export default function HomeLayout () {
    const location = useLocation();
    const { currentUser, loading } = useContext(UserContext)!;

    if (loading) {
        return <div className="loading-container">
                 <div className="loading"><div className="fi-loading"></div></div>
            </div>
    }

    if (!currentUser) {
        return <Navigate to="/sign-in" replace />;
    }

    const [page, setPage] = useState("Home");

    useEffect(() => {
        if (location.pathname.startsWith("/home")) {
            setPage("Home");
        } else if (location.pathname.startsWith("/notifications")){
            setPage("Notifications");
        } else if (location.pathname.startsWith("/organisations")){
            setPage("Organisations");
        } else if (location.pathname.startsWith("/profile")) {
            setPage("Profile")
        }

    }, [location.pathname])
    
    

    return (
        
        <div className="text-gray-800 flex flex-col h-screen outline-none">
            <nav className="hero-bg z-50 border-b sticky top-0">
                <NavBar />
            </nav>
                
            <main className="w-full flex-1 z-0 overflow-hidden">
                <Outlet />
            </main>
        </div>
    );
}