import { useCallback, useContext, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useUserPage } from "../hooks/useUser";
import "../assets/css/navbar.css";
import api from "../api";
import { UserContext } from "../context/userContext"
import { Navigate } from "react-router-dom";
import { setLoggingOut } from "../api";
// import { clearAccessToken } from "../hooks/useAuths";
import { Link } from "react-router-dom";
import axios from "axios";

export default function NavBar() {

    const location = useLocation();
    const {currentUser, error, loading} = useUserPage();
    const context = useContext(UserContext);
    const navigate = useNavigate()

    if (!context) throw new Error("UserContext not found");
    const { setCurrentUser } = context;
    const isOrgPage =   location.pathname.startsWith(`/dashboard`) || 
                        location.pathname.startsWith(`/staff`) ||
                        location.pathname.startsWith(`/payouts`) ||
                        location.pathname.startsWith(`/wallets`) ||
                        location.pathname.startsWith(`/reports`) ||
                        location.pathname.startsWith(`/settings`)

    const isActive = (path: string) => location.pathname.includes(path);
    const [ bxmenu, setMenu ] = useState(false);

    const activeStyle = {
        // background: "linear-gradient(90deg, rgba(255, 255, 255, 0.02), blue)" ,
        // justifyContent: "center",
        // display: "flex",
        // alignItems: "center",
        // color: "#ff3c00",
        // height: "100%",
        // padding: "3px",
        // borderRadius: "8px",
    }

    const inActiveStyle = {
        // background: "none",
        // borderBottom: "none",
        // justifyContent: "none",
        // display: "block",
        // alignItems: "none",
    }

    const [image, setImage] = useState<string | null>();

    const handlePic = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault()

        const file = e.target.files?.[0];

        if (file) {
            const url = URL.createObjectURL(file);
            setImage(url); 
        }
    }

    const handleLogout = useCallback( async () => {
            try {
                await api.post('/auths/logout')
            } catch (err) {}
            finally {  
                // clearAccessToken();
                setCurrentUser(null);
                setLoggingOut(false);
                delete api.defaults.headers.common["Authorization"];
                return <Navigate to="/sign-in" replace />
            }
        }, [navigate]);


    return (
        <div className="mx-auto py-2 px-5 flex items-center relative justify-between h-full">
            <div className="flex-1 items-center gap-4 w-[10%] flex-row">
                <div className="bg-gray-200 w-[60%] rounded-3xl flex pl-4">
                    <i className="bx bx-search text-4xl translate-y-[25%]"></i>
                    <input className="flex w-full p-4 rounded-3xl bg-gray-200 outline-none text-2xl" type="text" placeholder="Search Company"></input>
                </div>
            </div>
            {(!isOrgPage) && (
            <div className="flex text-xl text-center font-extrabold text-gray-200 font-semibold items-center w-auto gap-7 justify-between">
                <Link to={`/home/${currentUser?.uid}`} style={ isActive("home") ? activeStyle : inActiveStyle } className={isActive("home") ? "homelist" : ""}>Dashboard</Link>
                <Link to={`/notifications/${currentUser?.uid}`} style={ isActive("notifications") ? activeStyle : inActiveStyle } className={isActive("notifications") ? "homelist" : ""}>Notifications</Link>
                <Link to={`/organisations/${currentUser?.uid}`} style={ isActive("organisation") ? activeStyle : inActiveStyle } className={isActive("organisations") ? "homelist" : ""}>Createorg</Link> 
                {/* <Link to={`/${currentUser?.uid}/organisations`} style={ isActive("organisation") ? activeStyle : inActiveStyle } className={isActive("organisations") ? "homelist" : ""}>Join-Org</Link>  */}
                <Link to={`/profile/${currentUser?.uid}`} style={ isActive("profile") ? activeStyle : inActiveStyle } className={isActive("profile") ? "homelist" : ""}>Profile</Link>
                {/* <Link to={`/${currentUser?.uid}/organisations`} style={ isActive("organisation") ? activeStyle : inActiveStyle } className={isActive("organisations") ? "homelist" : ""}>Run-Payroll</Link> */}
            </div>
            )}
            {(isOrgPage) && (
            <>
                <li onClick={() => { navigate(`/dashboard/${currentUser?.uid}`)}} style={ isActive("dashboard") ? activeStyle : inActiveStyle } className={isActive("dashboard") ? "selected-comp" : ""}>Dashboard</li>
                <li onClick={() => { navigate(`/staff/${currentUser?.uid}`)}} style={ isActive("staff") ? activeStyle : inActiveStyle } className={isActive("staff") ? "selected-comp" : ""}>Staff</li> 
                <li onClick={() => { navigate(`/payouts/${currentUser?.uid}`)}} style={ isActive("payouts") ? activeStyle : inActiveStyle } className={isActive("payouts") ? "selected-comp" : ""}>Payouts</li>
                <li onClick={() => { navigate(`/wallet/${currentUser?.uid}`)}} style={ isActive("wallet") ? activeStyle : inActiveStyle } className={isActive("wallets") ? "selected-comp" : ""}>Wallets</li>
                <li onClick={() => { navigate(`/reports/${currentUser?.uid}`)}} style={ isActive("reports") ? activeStyle : inActiveStyle } className={isActive("reports") ? "selected-comp" : ""}>Reports</li> 
                <li onClick={() => { navigate(`/settings/${currentUser?.uid}`)}} style={ isActive("settings") ? activeStyle : inActiveStyle } className={isActive("settings") ? "selected-comp" : ""}>Settings</li>
            </>
            )}
            <div className="text-2xl flex-1 text-end font-bold text-gray-100">Strex<span className="text-blue-800">Pei</span></div>
            
                {/* 
                <i className="bx bx-menu text-2xl border text-blue-600 font-semibold px-7 py-3 rounded-sm hover:text-blue-700" onClick={() => setMenu(true)} />
                {(bxmenu === true) && (
                    <div className="nav-menu">
                        <div className="first-menu">
                            <i className="bx bxs-chevron-right chev-right" onClick={() => setMenu(false)}/>
                            <h1>My Profile</h1>
                            <i className="bx bx-cog"/>
                        </div>

                        <div className="second-layer">
                            <div className="second-top">
                                <div
                                    style={{
                                        backgroundImage: `url${image}`,
                                        backgroundPosition: "center",
                                        backgroundClip: "cover"
                                    }}

                                    className="image-div"
                                >
                                </div>

                                <span className="seco-span">
                                    <h1>{currentUser?.firstname} {currentUser?.lastname}</h1>
                                    <p>{currentUser?.email}</p>
                                    <button>Edit Profile</button>
                                </span>
                            </div>
                            <div className="h1s-div">
                                <span><h1><i className="bx bx-globe"/>Language</h1> <i className="bx bxs-chevron-right"/></span>
                                <span><h1><i className="bx bx-desktop"/>Display</h1><i className="bx bxs-chevron-right"/></span>
                                <span><h1><i className="bx bx-credit-card"/>Subscription</h1> <i className="bx bxs-chevron-right"/></span>
                                <hr />
                                <span><h1><i className="bx bx-trash-alt"/>Clear Cache</h1> <i className="bx bxs-chevron-right"/></span>
                                <span><h1><i className="bx bx-trash"/>Clear History</h1> <i className="bx bxs-chevron-right"/></span>
                                <span><h1><i className="bx bx-log-out"/>Log Out</h1> <i className="bx bxs-chevron-right" onClick={handleLogout}/></span>
                            </div>
                        </div>
                    </div>
                )} */}
        </div>
    );
}