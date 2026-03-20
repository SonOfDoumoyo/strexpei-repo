import axios from "axios";
import { useState, type HtmlHTMLAttributes, useEffect } from "react";
import { useActionData, useNavigate } from 'react-router-dom';
import 'boxicons/css/boxicons.min.css';
import '../assets/css/main.css';
import '../assets/css/home.css';
import '../assets/css/form.css';
import logo from '../assets/images/strexpei-logo.png';
import { getUser } from "../context/userContext";
import { useCompanyPage } from "../hooks/useCompany";
import type { Company } from "../schemas/CompanyTypes";
import type { User } from "../schemas/authTypes";
import { useUserPage } from "../hooks/useUser";
import { useUser } from "../context/userContext";
import Notification from "./Notify";
import { ResendCountdown } from "./coundowner";

function Home () {
    
    const { currentUser, error, loading } = useUserPage();
    const [ isSelected, setIsSelected] = useState(false);
    const [comp, setComp] = useState<Company[]>([]);
    const [selectedCompany, setSelectedCompany] = useState<OrgMembership | null>(null);
    const [active, setActive] = useState("home");
    const [compChosen, setCompChosen] = useState(false);
    console.log(currentUser);

    type OrgMembership = { role: "Manager" | "Staff"; cid: string; company_name: string; members: number; };

    type OrgStatus = { status: string ; cid: string; company_name: string; };
    console.log(currentUser);
    const memberships: OrgMembership[] = [
        ...(currentUser?.companies ?? []).map(c => ({
            role: "Manager" as const,
            cid: c.cid,
            company_name: c.company_name,
            members: c.staffs.length ?? 0,
        })),

        ...(currentUser?.staffs ?? []).map(s => ({
            role: "Staff" as const,
            cid: s.company_id,
            company_name: s.company?.company_name,
            members: s.company?.staffs.length ?? 0,
        })),
    ]

    const requeststatus: OrgStatus[] = [
        ...(currentUser?.request ?? []).map(r => ({
            status: r.status,
            cid: r.company_id,
            company_name: r.company_name,
        }))
    ]


    return (
        <div className="screen">
            <div className="card home-box">
                    <div className="nav-bar">
                        <div className="navbar">

                            <div className="home-logo">
                                <img src={logo} alt="Logo" className="log home-log"/>
                                <h1>trexpei</h1>
                            </div>


                            <div className="list-box">
                                <nav className="list-items">
                                    <ul>
                                        {(compChosen === false  ) && (
                                        <>
                                            <li onClick={() => setActive("home")} style={{ background: active === "home" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="home-list"><i className={`bx ${active === "home" ? "bxs-home":"bx-home"} right-icon`}/>Home</li>
                                            <li onClick={() => setActive("notifications")} style={{ background: active === "notifications" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="home-list"><i className={`bx ${active === "notifications" ? "bxs-bell":"bx-bell"} right-icon`}/>Notifications</li>
                                            <li onClick={() => setActive("organisation")} style={{ background: active === "organisation" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="home-list"><i className={`bx ${active === "organisation"? "bxs-briefcase":"bx-briefcase"} right-icon`}/>Organisations</li> 
                                            <li onClick={() => setActive("profile")} style={{ background: active === "profile" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="home-list"><i className={`bx ${active === "profile" ? "bxs-user":"bx-user"} right-icon`}/>Profile</li>
                                        </>
                                        )}
                                        {(compChosen !== false) && (
                                        <>
                                            <li onClick={() => setActive("dashboard")} style={{ background: active === "dashboard" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="selected-comp"><i className="bx bxs-grid-alt right-icon"/>Dashboard</li>
                                            <li onClick={() => setActive("staff")} style={{ background: active === "staff" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="selected-comp"><i className="bx bxs-group right-icon"/>Staff</li> 
                                            <li onClick={() => setActive("payouts")} style={{ background: active === "payouts" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="selected-comp"><i className="bx bx-money-withdraw right-icon"/>Payouts</li>
                                            <li onClick={() => setActive("wallet")} style={{ background: active === "wallet" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="selected-comp"><i className="bx bxs-wallet right-icon"/>Wallets</li>
                                            <li onClick={() => setActive("reports")} style={{ background: active === "reports" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="selected-comp"><i className="bx bxs-bar-chart-alt-2 right-icon"/>Reports</li> 
                                            <li onClick={() => setActive("settings")} style={{ background: active === "settings" ? "linear-gradient(90deg, rgba(255, 255, 255, 0.02), #ff3c0042)" : "none" }} className="selected-comp"><i className="bx bxs-cog right-icon"/>Settings</li>
                                        </>
                                        )}
                                    </ul>
                                </nav>
                            </div>
                        
                        </div>
                    </div>

                    <div className="all-page">
                        <div className="upper-head">
                            <select value={selectedCompany?.cid || ""} onChange={(e) => {
                                const picked = memberships?.find(
                                    c => c.cid === e.target.value
                                ) || null;
                                setSelectedCompany(picked);
                                setIsSelected(Boolean(picked));
                                setCompChosen(Boolean(picked));
                                if (picked){
                                    setActive("dashboard");
                                }else{
                                    setActive("home");
                                }
                                }} 
                                className="select-box"
                            >

                                {(memberships?.length > 1) && (<option value="" className="main-select">Select Company</option>)}
                                {memberships?.map((company) => (
                                    <option key={company.cid} value={company.cid} className="option-box">
                                        {company.company_name} . {company.role}
                                    </option>
                                ))}
                                
                            </select>
                            {(compChosen === true) && (<button className="back-btn manager-btn" type="button" onClick={() => {
                                setSelectedCompany(null);
                                setActive("home");
                                setCompChosen(false);
                            }}>back</button>)}

                            <p><i className="bx bx-user left-icon"/>{getUser()?.user_email}<i className="bx bxs-user right-i"/></p>
                        </div>

                        {(compChosen === false) && (active == "home") && (<div className="lower-page">
                            <h1 className="welc-header">Welcome, {currentUser?.firstname}</h1>
                            <p className="ur-orgs">Select an organisation to continue</p>

                            <div className="first-lowerp">
                                {memberships.map((company) => (
                                <div className="company-box" key={company.cid}>
                        
                                    <p>{company.company_name}</p>
                                    <p className="staff-number">{company.members} Members</p>
                                    <button className="manager-btn" onClick={() => {setCompChosen(true); setSelectedCompany(company); setActive("dashboard")}}><i className="bx bxs-user right-i"/>{company.role}</button>

                                </div>))}
                            </div>
                        </div>)}

                        {(active == "notifications") && (
                            <Notification/>
                        )}
                    </div>

                    <div className="dashboard-page">
                    </div>
            </div>

        </div>
    );
}

export default Home;