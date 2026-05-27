import axios from "axios";
import React, { useState, type HtmlHTMLAttributes, useEffect, useRef, type SyntheticEvent } from "react";
import { Outlet, useActionData, useNavigate } from 'react-router-dom';
import 'boxicons/css/boxicons.min.css';
import logo from '../assets/images/strexpei-logo.png';
import { useCompanyPage } from "../hooks/useCompany";
import type { Company } from "../schemas/CompanyTypes";
import type { User } from "../schemas/authTypes";
import { useUserPage } from "../hooks/useUser";
import "../assets/css/home.css";
import useTimeOfDay from "../utils/useTimeday";
import useDateOfDay from "../utils/useDate";
import { useParams } from "react-router-dom";
import { useUser } from "../context/userContext";
import api from "../api";
import { getCurrentUid, setCurrentUid } from "../hooks/currentUid";

function Home () {
    
    const { currentUser, error, loading } = useUserPage();
    const [ editingId, setEditingId ] = useState<string | null>(null);
    const [ clickedEdit, setClickedEdit ] = useState(false);
    const selected = "Select Company";
    const [ occurederror, setError ] = useState("");
    const { fetchUser } = useUser();

    const [ selectedSIdeBAr, setSelectedSideBar ] = useState(() => {
        const ssideb = sessionStorage.getItem(`sideBar_${getCurrentUid()}`)
        return ssideb ? ssideb : ""
    });
    
    const [comp, setComp] = useState<Company[]>([]);

    const [selectedCompany, setSelectedCompany] = useState<OrgMembership | null>(() => {
        const saved = sessionStorage.getItem(`selectedCompany_${getCurrentUid()}`)
        return saved ? JSON.parse(saved) : null
    });

    const [compChosen, setCompChosen] = useState(() => {
        const stored = sessionStorage.getItem(`comp_${getCurrentUid()}`)
        return stored ? JSON.parse(stored) : false
    });
    const [sidebar, setSideBar ] = useState(true);
    const timeOfDay = useTimeOfDay();
    const dateOfDay = useDateOfDay();
    const [ activeStaff, setActiveStaff ] = useState(0);
    // const [staffsSalary, setStaffsSalary] = useState(0);
    console.log(currentUser);

    useEffect(() => {
        sessionStorage.setItem(
            `selectedCompany_${getCurrentUid()}`, JSON.stringify(selectedCompany)
        )
        setClickedEdit(false);
    }, [selectedCompany])

    useEffect(() => {
        sessionStorage.setItem(`comp_${getCurrentUid()}`, JSON.stringify(compChosen))
    }, [compChosen])

    useEffect(() => {
        setDraftData(setDD());
    }, [selectedCompany]);

    const handleSideBarChosen = (sideBar_: string) => {
        setSelectedSideBar(sideBar_);

        sessionStorage.setItem(
            `sideBar_${getCurrentUid()}`, sideBar_
        )
    }

    


    const companyIndex = currentUser?.companies?.findIndex(
        (company) => company.cid === selectedCompany?.cid
    ) ?? null;

    const finalIndex = companyIndex !== -1 ? companyIndex : null;
    const selectedOrg = finalIndex !== null ? currentUser?.companies?.[finalIndex] : null;
    const [staffDrafts, setStaffDrafts] = useState<Record<string, any>>({});


    type DraftCompany = {
        role: string;
        company_name: string;
        address: string;
    }



    //draft data for inputs
    const [ draftData, setDraftData ] = useState<DraftCompany>({
        role: selectedCompany?.role ?? "",
        company_name: selectedCompany?.company_name ?? "",
        address: selectedCompany?.address ?? "",
    });

    const staffCompanyIndex = (cid: string) => {
        return currentUser?.companies?.findIndex(
            (company) => company.cid === cid
        ) ?? null;
    }

    const navigate = useNavigate();

    const payoutTotal = (cid: string) => {
        const finalIndex_2 = staffCompanyIndex(cid) !== -1 ? staffCompanyIndex(cid) : null;
        return finalIndex_2 !== null ? currentUser?.companies?.[finalIndex_2] : null;
    }

    //handleEdit
    const handleEdit = () => {
        setDraftData({
            role: selectedCompany?.role ?? "",
            company_name: selectedCompany?.company_name ?? "",
            address: selectedCompany?.address ?? ""
        })
        setClickedEdit(true);
    }

    const handleEditStaff = (staff: any) => {
        setEditingId(staff.sid);

        setStaffDrafts(prev => ({
            ...prev,
            [staff.sid]: { ...staff }
        }));
    };


    //handling change of input 
    const handleStaffChange = (
        e: React.ChangeEvent<HTMLInputElement>,
        staffId: string
    ) => {
        const { name, value } = e.target;

        setStaffDrafts(prev => ({
            ...prev,
            [staffId]: {
                ...prev[staffId],
                [name]: value
            }
        }));
    };



    const handleDraftChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setDraftData((prev) => ({
            ...prev, [name]:value
        }));
    }

    const setDD = () => {
        return {
            role: draftData.role ?? "",
            company_name: draftData.company_name ?? "",
            address: draftData.address ?? "",
        }
    }

    const handleSave = async () => {
        if (!selectedCompany) return;

        setSelectedCompany({
            ...selectedCompany,
            role: draftData.role as "Manager" | "Staff",
            company_name: draftData.company_name,
            address: draftData.address,
        })

        setStaffDrafts(prev => {
            console.log(prev)
            return Object.entries(prev).map(([sid, staff]) => {
                const draft = prev[sid];
                if (!draft) return staff;
                
                return {
                    // ...staffCompanyIndex,
                    ...draft
                }
            })
        })
        try{
            const resp_1 = await api.patch(
            `/company/update_company_data/${selectedCompany.cid}`, draftData
            )

            Object.entries(staffDrafts).map( async ([sid, staff]) => {
                const resp_2 = await api.patch(`/staffs/update_staff/${sid}`, staffDrafts[sid])
                const updatedStaff = staffDrafts[sid];
            })

        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err?.response?.data || "Update failed!")
            } else {
                setError("Server Not Reachable")
            }

        } finally {
            await fetchUser();
        }
        setStaffDrafts({});
        setEditingId(null);
        setClickedEdit(false)
    }

    const handleCancel = () => {
        setDraftData({
            role: selectedCompany?.role ?? "",
            company_name: selectedCompany?.company_name ?? "",
            address: selectedCompany?.address ?? ""
        });
        setStaffDrafts({})
        setEditingId(null)
        setClickedEdit(false);
    }

    // const resetForm = () => {
    //     setCompFormData({
    //         role: String(selectedCompany?.role ?? ""),
    //         company_name: String(selectedCompany?.company_name ?? ""),
    //         address: String(selectedCompany?.address ?? ""),
    //     });
    // };

    //copy company id
    const inputRef = useRef<HTMLInputElement>(null);
    const copyText = () => {
        if (inputRef.current) {
            navigator.clipboard.writeText(inputRef.current.value);
        }
    }

    type OrgStatus = { status: string ; cid: string; company_name: string; position: string; token: string; firstname: string; lastname: string};
    type OrgMembership = { role: "Manager" | "Staff"; cid: string; company_name: string; members: number; address: string; createdAt: string; requests?: OrgStatus[];};

    
    // console.log(currentUser);
    const memberships: OrgMembership[] = [
        ...(currentUser?.companies ?? []).map(c => ({
            role: "Manager" as const,
            cid: c.cid,
            company_name: c.company_name,
            members: c.staffs.length ?? 0,
            address: c.address,
            createdAt: c.created_at,
            requests: c.request.map(r => ({
                status: r.status,
                cid: r.company_id,
                company_name: r.company_name,
                position: r.position,
                token: r.token,
                firstname: r.firstname,
                lastname: r.lastname,
            }))
        })),

        ...(currentUser?.staffs ?? []).map(s => ({
            role: "Staff" as const,
            cid: s.company_id,
            company_name: s.company?.company_name,
            members: s.company?.staffs.length ?? 0,
            address: s.company.address,
            createdAt: s.company.created_at,
        })),
    ]

    // const requeststatus: OrgStatus[] = [
    //     ...(currentUser?.request ?? []).map(r => ({
    //         status: r.status,
    //         cid: r.company_id,
    //         company_name: r.company_name,
    //     }))
    // ]

    const pendingRequest = [...(currentUser?.companies ?? []).flatMap(r => 
        (r.request)
    )].length

    const totalSalary = selectedOrg?.staffs.reduce((acc, staff) => acc + Number(staff.salary), 0) || 0;

    

    const [ dropDown, setDropDown ] = useState(false);
    const [ image, setImage ] = useState<string | null>(null);

    const handlePicChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();

        const file = e.target.files?.[0]; // pick first file
        if (file) {
            const url = URL.createObjectURL(file);
            setImage(url); //base64 string
        }

    }

    const getRequestUser = async (sender_id: string) => {
        const response = await api.get(`/worker/get_a_user/${sender_id}`)
    }

    return (
        <div className="flex bg-gray-200 h-full overflow-hidden">
            
            {/* <div className={`${ active === "home" ? "upper-head" : "no-menu"}`}>

                <input type="file" accept="image/*" onChange={handlePicChange}/> */}
                {/* <div className="dispImg" style={{
                    backgroundImage: `url(${image})`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                }}>
                    {!image && <span>Preview here</span>}
                </div> */}
                {/* 

                    {(memberships?.length > 1) && (<option value="" className="main-select">Select Company</option>)}
                    {memberships?.map((company) => (
                        <option key={company.cid} value={company.cid} className="option-box">
                            {company.company_name} . {company.role}
                        </option>
                    ))}
                    <option className="opt-plus">
                        <p><i className="bx bx-plus"></i>Add or Join</p>
                    </option>
                    
                </select>
                {(compChosen === true) && (<button className="back-btn manager-btn" type="button" onClick={() => {
                    setSelectedCompany(null);
                    setActive("home");
                    setCompChosen(false);
                }}>back</button>)} */}

                {/* <p><i className="bx bx-user left-icon"/>{getUser()?.user_email}<i className="bx bxs-user right-i"/></p> */}
                
            {/* </div> */}
            {(sidebar === true) && <div className="w-[250px] transition-all border-b-black bg-gray-500 duration-300 border-r overflow-y-auto">
               
                <div className="flex flex-col justify-between overflow-y-auto gap-10 p-0 h-[100%] w-[100%]">
                    <div className="flex justify-between flex-col gap-6">
                        <div className="p-7 relative w-full">
                            <div className="flex justify-between flex-col align-middle items-center cursor-pointer rounded-xl shadow-[0px_0px_20px_rgba(41,43,47,0.3)]">
                                <div className="w-full bg-gray-100 p-5 font-bold text-xl rounded-md items-center flex justify-between">
                                    {(compChosen === false) && <span>{selected}</span>}
                                    {(compChosen == true) && (
                                        <div className="flex items-center justify-between gap-3">
                                            <span className="rounded-[50%] p-8 w-4 h-4 bg-blue-950 text-white flex justify-center items-center">{selectedCompany?.company_name.charAt(0)}</span>
                                            <div className="">
                                                <h2>{selectedCompany?.company_name}</h2>
                                                <p className="text-base font-semibold text-gray-600">{selectedCompany?.role}</p>
                                            </div>
                                        </div>
                                    )

                                    }
                                    <i className="bx bxs-chevron-down" onClick={() => setDropDown(!dropDown)}/>
                                </div>
                            </div>
                            {(dropDown == true) && (<div className="z-10 absolute w-fit right-0 flex border-r border-gray-800 shadow-[0px_0px_20px_rgba(30,58,138,0.6)] rounded-md flex-col bg-blue-600 font-bold overflow-ellipsis">
                                {memberships.map((company) => (
                                    <ul className="text-xl">
                                        <li className="hover:bg-gray-600 text-gray-100 p-5 cursor-pointer transition" onClick={() => {setCompChosen(true); setSelectedCompany(company); setDropDown(false);}}>{company.company_name} . {company.role}</li>
                                    </ul>
                                ))}
                            </div>)}
                        </div>

                        {(selectedCompany?.role == "Manager") &&(<div className="flex flex-col justify-between gap-12 cursor-default">
                            <div className="flex flex-col justify-between">
                                <span className="text-xl font-black text-gray-400 px-7">WORKSPACE</span>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "overview" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("overview")}><i className={`bx bxs-home ${selectedSIdeBAr === "overview" ? "text-blue-600" : "text-white"}`}></i>Overview</div>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "staff" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("staff")}><i className={`bx bxs-group ${selectedSIdeBAr === "staff" ? "text-blue-600" : "text-white"}`}></i>Staff</div>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "runpayroll" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("runpayroll")}><i className={`bx bxs-credit-card ${selectedSIdeBAr === "runpayroll" ? "text-blue-600" : "text-white"}`}></i>Run Payroll</div>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "payrollhistory" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("payrollhistory")}><i className={`bx bxs-time ${selectedSIdeBAr === "payrollhistory" ? "text-blue-600" : "text-white"}`}></i>Payroll History</div>
                            </div>
                            
                            <div className="flex flex-col justify-between">
                                <span className="text-xl font-black text-gray-400 px-7">FINANCE</span>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "analytics" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("analytics")}><i className={`bx bxs-bar-chart-alt-2 ${selectedSIdeBAr === "analytics" ? "text-blue-600" : "text-white"}`}></i>Analytics</div>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "reports" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("reports")}><i className={`bx bxs-file-doc ${selectedSIdeBAr === "reports" ? "text-blue-600" : "text-white"}`}></i>Reports</div>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "bankaccounts" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("bankaccounts")}><i className={`bx bxs-bank ${selectedSIdeBAr === "bankaccounts" ? "text-blue-600" : "text-white"}`}></i>Bank Accounts</div>
                            </div>

                            <div className="flex flex-col justify-between">
                                <span className="text-xl font-black text-gray-400 px-7">ORG</span>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "requests" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("requests")}><i className={`bx bxs-message-square-detail ${selectedSIdeBAr === "requests" ? "text-blue-600" : "text-white"}`}></i>Requests</div>
                                <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "settings" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("settings")}><i className={`bx bxs-cog ${selectedSIdeBAr === "settings" ? "text-blue-600" : "text-white"}`}></i>Settings</div>
                            </div>
                            
                        </div>)}
                        {(selectedCompany?.role === "Staff") && (
                            <div className="flex flex-col justify-between gap-12 cursor-default">
                                <div className="flex flex-col justify-between">
                                    <span className="text-xl font-black text-gray-400 px-7">WORKSPACE</span>
                                    <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "overview" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("overview")}><i className={`bx bxs-home ${selectedSIdeBAr === "overview" ? "text-blue-600" : "text-white"}`}></i>Overview</div>
                                    <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "payslips" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("payslips")}><i className={`bx bxs-credit-card ${selectedSIdeBAr === "payslips" ? "text-blue-600" : "text-white"}`}></i>Payslips</div>
                                    <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "leaverequests" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("leaverequests")}><i className={`bx bxs-time ${selectedSIdeBAr === "leaverequests" ? "text-blue-600" : "text-white"}`}></i>Leave Requests</div>
                                    <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "attendance" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("attendance")}><i className={`bx bxs-credit-card ${selectedSIdeBAr === "attendance" ? "text-blue-600" : "text-white"}`}></i>Attendance</div>
                                    <div className={`text-2xl font-semibold cursor-pointer text-gray-100 py-5 px-7 hover:bg-gray-600 active:bg-gray-500 items-center gap-4 flex ${selectedSIdeBAr === "settings" ? "activeBar" : ""}`} onClick={() => handleSideBarChosen("settings")}><i className={`bx bxs-cog ${selectedSIdeBAr === "settings" ? "text-blue-600" : "text-white"}`}></i>Settings</div>
                                </div>
                            </div>
                        )}
                    </div>
                    
                    <div className="flex py-6 w-full px-7 border-t text-gray-400 items-center justify-between gap-4 cursor-pointer">
                        
                        <span className="bg-blue-950 p-8 rounded-[50%] text-white font-semibold">
                            {currentUser?.firstname?.charAt(0)}{currentUser?.lastname?.charAt(0)}
                        </span>
                        <div>
                            <h2 className="text-gray-100 text-2xl font-bold">{currentUser?.firstname} {currentUser?.lastname}</h2>
                            <p className="text-gray-400">{currentUser?.email}</p>
                        </div>
                        <i className="bx bx-dots-horizontal-rounded text-4xl"/>
                    </div>
                </div> 
            </div>}

            <div className="flex-1 p-6 overflow-y-auto min-w-0 flex flex-col">
                <div>
                    <div className="absolute -translate-y-1/2 top-1/2 p-6 bg-gray-400 w-11 h-11 flex justify-center items-center rounded-[50%] cursor-pointer font-bold text-4xl shadow-[0px_0px_20px_rgba(41,43,47,0.5)] hover:shadow-[0px_0px_20px_rgba(41,43,47,0.7)] z-10 transition" onClick={() => setSideBar(!sidebar)}>
                        {(sidebar === false) && <i className="bx bxs-chevron-right text-gray-300"/>}
                        {(sidebar === true) && <i className="bx bxs-chevron-left text-gray-500" />}
                    </div>
                    {(selectedSIdeBAr === "overview") && <div className="flex flex-row justify-between items-center">
                        <span className="flex gap-3 flex-col">
                            <div className="text-5xl font-bold text-gray-500"> <h1 className="welc-header">Good {timeOfDay}, <span className="text-gray-700">{currentUser?.firstname}</span></h1></div>
                            <p className="text-xl text-gray-500 flex gap-3">{dateOfDay} <span className="font-bold">{selectedCompany?.company_name}</span></p>
                        </span>
                        {/* <span className="flex flex-row justify-between gap-7 text-2xl items-center">
                            <div className="inline-flex text-xl cursor-pointer">🔔<span className="w-[4px] h-[4px] bg-red-700 rounded-full animate-pulse"></span></div>
                            <div className="border border-gray-100 rounded-[6px] p-4 px-5 cursor-pointer">+ Invite Staff</div>
                            <div className="bg-blue-300 text-gray-900 font-semibold rounded-[6px] p-4 px-8 cursor-pointer">Run Payroll</div>
                        </span> */}
                    </div>}
                </div>

                {(compChosen === false) && (
                    <div className="flex flex-col gap-[1%] cursor-default">
                        
                        {/* Workspaces */}
                        <div className="grid md:grid-cols-2 lg:grid-cols-2 gap-8">
                            {memberships.map((company) => (
                                <div className="card-bg flex flex-col w-[100%] justify-between p-8 rounded-xl h-[30vh] text-white shadow-[0px_0px_10px_rgba(41,43,47,0.5)]">
                                    <div className="font-black text-3xl text-white flex justify-between">{company.company_name}
                                         <h1 className="">Role: {company.role}</h1>
                                    </div>
                                    <div>
                                        <div className="font-semibold text-2xl text-[#00379d]">
                                            {(company.role === "Manager") && (
                                                <div>
                                                    <div>{company.members} Staff Members</div>
                                                    <div>
                                                    Monthly Payroll: &#8358;{payoutTotal(company.cid)?.staffs.reduce((acc, staff) => acc + Number(staff.salary), 0) || 0}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                        <div>
                                            <button className="text-[#00379d] font-bold text-4xl">Open Workspace</button>
                                        </div>
                                    </div>
                                </div>

                                
                            ))}
                            <div className="grid md:grid-cols-2 lg:grid-cols-2 gap-8 rounded-xl text-2xl font-bold text-[#7e7e7f]">
                                <h1 className="bg-[#010c28] p-12 rounded-xl shadow-[0px_0px_10px_rgba(41,43,47,0.5)] w-[100%] flex justify-center items-center">Companies Joined  (<span className="text-white">{(currentUser?.companies?.length!) + (currentUser?.staffs?.length!)}</span>)</h1>
                                <h1 className="bg-[#010c28] p-12 rounded-xl shadow-[0px_0px_10px_rgba(41,43,47,0.5)] w-[100%] flex justify-center items-center">Organization Managed (<span className="text-white">{currentUser?.companies?.length}</span>)</h1>
                                <button className="bg-[#010c28] p-12 rounded-xl shadow-[0px_0px_10px_rgba(41,43,47,0.5)] w-[100%] flex justify-center items-center" onClick={() => navigate(`/workspace/join-company/${getCurrentUid()}`)}>Join +</button>
                                <button className="bg-[#010c28] p-12 rounded-xl shadow-[0px_0px_10px_rgba(41,43,47,0.5)] w-[100%] flex justify-center items-center" onClick={() => navigate(`/workspace/create-company/${getCurrentUid()}`)}>Create</button>
                            </div>
                        </div>
                        
                    </div>
                )}

                {(selectedCompany?.role === "Manager" && selectedSIdeBAr === "overview" && compChosen === true) && (
                <div className="flex flex-col gap-[4%]">
                    <div className="flex gap-[2%]">
                        <div className="first-cards flex bg-white w-[30%] flex-col p-12 rounded-xl gap-2  shadow-[0px_0px_20px_rgba(41,43,47,0.2)]">
                            <h2 className="font-mono text-xl font-semibold text-gray-500">TOTAL DISBURSED</h2>
                            <h1 className="text-5xl">&#8358;0.00</h1>
                            <p className="text-base text-green-500">0.00% this quarter</p>
                        </div>

                        <div className="first-cards flex bg-white w-[30%] flex-col p-12 rounded-xl gap-2  shadow-[0px_0px_20px_rgba(41,43,47,0.2)]">
                            <h2 className="font-mono text-xl font-semibold text-gray-500">ACTIVE STAFF</h2>
                            <h1 className="text-5xl">{selectedCompany?.members}</h1>
                            <p className="text-base text-green-500">No staff added this month</p>
                        </div>

                        <div className="first-cards flex bg-white w-[30%] flex-col p-12 rounded-xl gap-2  shadow-[0px_0px_20px_rgba(41,43,47,0.2)]">
                            <h2 className="font-mono text-xl font-semibold text-gray-500">LAST PAYROLL</h2>
                            <h1 className="text-5xl">&#8358;0.00</h1>
                            <p className="text-base text-gray-500">null</p>
                        </div>

                        <div className="first-cards flex bg-white w-[30%] flex-col p-12 rounded-xl gap-2  shadow-[0px_0px_20px_rgba(41,43,47,0.2)]">
                            <h2 className="font-mono text-xl font-semibold text-gray-500">PENDING REQUESTS</h2>
                            <h1 className="text-5xl">0</h1>
                            <p className="text-base text-green-500">0.00% this quarter</p>
                        </div>
                    </div>

                    <div className="flex flex-row w-full gap-[2%] h-full">
                        <div className="flex-1 w-full flex flex-col gap-[3%]">
                            <div className="bg-white shadow-[0px_0px_20px_rgba(41,43,47,0.2)] rounded-xl">
                                <div>
                                    <div className="flex flex-row justify-between items-center p-8">
                                        <div className="">
                                            <h1 className="text-xl font-semibold">Monthly Payroll Disbursement</h1>
                                            <p className="text-base text-gray-500">Last 6 months . Nigerian Naira (N)</p>
                                        </div>
                                        <p className="text-base font-medium text-gray-500">Export</p>
                                    </div>
                                    <div className="flex-1 h-px bg-gray-300"></div>
                                </div>
                                <div className="flex relative w-full justify-between p-8">
                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Jan</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Feb</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Mar</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Apr</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">May</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Jun</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Jul</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Aug</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Sep</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Oct</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Nov</p>
                                    </div>

                                    <div className="flex flex-col h-full justify-between">
                                        <div className="h-[250px]"></div>
                                        <p className="text-base font-medium text-gray-500">Dec</p>
                                    </div>
                                </div>
                            </div>
                            <div className="bg-white shadow-[0px_0px_20px_rgba(41,43,47,0.2)] rounded-xl">
                                <div>
                                    <div className="flex flex-row justify-between items-center p-8">
                                        <div className="">
                                            <h1 className="text-xl font-semibold">Staff - Last Payroll</h1>
                                            <p className="text-base text-gray-500">null . {activeStaff}</p>
                                        </div>
                                        <p className="text-base font-medium text-gray-500">View All</p>
                                    </div>
                                </div>
                                <div className="w-full">
                                    <div className="flex w-full text-xl p-8 font-semibold text-gray-500 bg-gray-200">
                                        <h2 className="w-[25%]">EMPLOYEE</h2>
                                        <h2 className="w-[20%]">ROLE</h2>
                                        <h2 className="w-[20%]">AMOUNT</h2>
                                        <h2 className="w-[20%]">STATUS</h2>
                                    </div>

                                    {
                                    selectedOrg?.staffs?.map((staff) => (
                                        <div className="flex p-8 text-xl items-center">
                                            <div className="w-[25%] flex flex-row items-center gap-[10px]">
                                                <span className="bg-blue-600 text-white font-bold items-center justify-center flex w-[40px] h-[40px] rounded-[50%]">
                                                    {staff.firstname.charAt(0)}{staff.lastname.charAt(0)}
                                                </span>
                                                
                                                <span className="flex flex-col">
                                                    <p className="text-xl font-semibold">{staff.firstname} {staff.lastname}</p>
                                                    <p className="text-gray-500">{staff.position}</p>
                                                </span>
                                                </div>
                                                
                                            <div className="w-[20%] text-gray-500">{staff.position}</div>
                                            <div className="w-[20%]">&#8358;{staff.salary}</div>
                                            <div className="w-[20%]">hehe</div>
                                        </div>
                                    ))
                                    }
                                </div>

                            </div>
                        </div>
                        <div className="w-[40%] text-gray-200">
                            <div className="hero-bg p-8 flex flex-col gap-6 rounded-xl">
                                <h2 className="text-2xl text-blue-500">NEXT PAYROLL</h2>
                                <h1 className="text-5xl text-white font-semibold">&#8358;{totalSalary}</h1>
                                <p className="text-xl">Scheduled . April 30, 2026 . 12 staff</p>
                                <div>progress bar</div>
                                <div className="flex justify-between">
                                    <p>Cycle Progress</p>
                                    <p>72% complete</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>)}

                {(selectedSIdeBAr === "settings") && (
                    <div className="flex flex-col overflow-x-hidden gap-14 relative">
                        
                        <div className="w-full flex flex-col gap-2">
                            <p className="text-5xl mb-[40px]"><span className="font-black">Manage  - {selectedCompany?.company_name}</span></p>
                            
                            <div className="flex flex-col gap-3">
                                <p className="text-3xl font-semibold flex justify-between w-full"><span>Company ID</span></p>
                                <div className="flex relative"><input ref={inputRef} className="text-xl rounded-xl bg-gray-600 w-full outline-none border border-spacing-2 border-gray-300 text-gray-400 p-4" type="text" value={selectedCompany?.cid} readOnly></input><i className="bx bxs-copy text-gray-300 cursor-pointer absolute text-3xl flex float-right right-4 top-[30%]" onClick={copyText}/></div>
                            </div>

                            <div className="flex flex-col gap-5">

                                <div className="flex flex-col gap-3">
                                    <p className="text-3xl font-semibold flex justify-between w-full">Your Position</p>
                                    <div className="flex relative"><input type="text" name="role" value={draftData?.role ?? ""} onChange={handleDraftChange} onClick={() => {setClickedEdit(!clickedEdit); setDraftData(setDD()); handleEdit();}} readOnly={!clickedEdit} className="text-xl w-full rounded-xl outline-none border border-spacing-2 border-gray-300 bg-transparent text-gray-400 p-4"/>{clickedEdit === false && <i className="bx bxs-edit text-gray-300 cursor-pointer absolute text-3xl flex float-right right-4 top-[30%]" onClick={() => {setClickedEdit(!clickedEdit); setDraftData(setDD()); handleEdit();}}/>}</div>
                                </div> 

                                <div className="flex flex-col gap-3">
                                    <p className="text-3xl font-semibold flex justify-between w-full">Company Name</p>
                                    <div className="flex relative"><input type="text" name="company_name" value={clickedEdit === false ? selectedCompany?.company_name : draftData?.company_name ?? ""} onChange={handleDraftChange} onClick={() => {setClickedEdit(true); setDraftData(setDD()); handleEdit();}} readOnly={!clickedEdit} className="text-xl w-full rounded-xl outline-none border border-spacing-2 border-gray-300 bg-transparent text-gray-400 p-4"/>{clickedEdit === false && <i className="bx bxs-edit text-gray-300 cursor-pointer absolute text-3xl flex float-right right-4 top-[30%]" onClick={() => {setClickedEdit(!clickedEdit); setDraftData(setDD()); handleEdit();}}/>}</div>
                                </div>
                                <div className="flex flex-col gap-3">
                                    <p className="text-3xl font-semibold flex justify-between w-full">Company Address</p>
                                    <div className="flex relative"><input type="text" name="address" value={draftData?.address ?? ""} onChange={handleDraftChange} onClick={() => {setClickedEdit(true); setDraftData(setDD()); handleEdit();}} readOnly={!clickedEdit} className="text-xl w-full rounded-xl outline-none border border-spacing-2 border-gray-300 bg-transparent text-gray-400 p-4"/>{clickedEdit === false && <i className="bx bxs-edit text-gray-300 cursor-pointer absolute text-3xl flex float-right right-4 top-[30%]" onClick={() => {setClickedEdit(!clickedEdit); setDraftData(setDD()); handleEdit();}}/>}</div>
                                </div>
                            
                            </div>

                            <div className="flex flex-col gap-3">
                                <p className="text-3xl font-semibold flex justify-between w-full">Joined Strexpei</p>
                                <input className="text-xl rounded-xl bg-gray-600 outline-none border border-spacing-2 border-gray-300 text-gray-400 p-4" type="text" value={selectedCompany?.createdAt} readOnly></input>
                            </div>
                        </div>
                        
                        <div className="w-full p-6">
                                <p className="text-4xl font-black">Manage {selectedCompany?.company_name} Staffs</p>
                            <div className="grid md:grid-cols-2 lg:grid-cols-2 gap-8">
                                {selectedOrg?.staffs?.map(staffs => {
                                    const draft = staffDrafts[staffs.sid];
                                    return (
                                    <div className="w-full p-6 rounded-2xl shadow-[0px_0px_10px_rgba(41,43,47,0.2)]">
                                        <div className="flex flex-row w-full gap-6">
                                            <div className="flex flex-col w-full">
                                                <p className="text-2xl font-semibold">Name</p>
                                                <input className="text-2xl rounded-xl outline-none  bg-blue-600 text-gray-900 font-bold p-4" type="text" value={staffs.firstname +" "+ staffs.lastname} readOnly></input>
                                            </div>
                                            <div className="flex flex-col w-full">
                                                <p className="text-2xl font-semibold">Role</p>
                                                <div className="flex relative"><input className="text-2xl w-full rounded-xl outline-none text-gray-900 font-bold p-4" type="text" key={`role_${staffs.sid}`} value={editingId ? draft?.role ?? staffs.position : staffs.position} name="role" readOnly={!clickedEdit} onChange={(e) => handleStaffChange(e, staffs.sid)} onClick={() => {setEditingId(`role_${staffs.sid}`); setClickedEdit(true); handleEditStaff(staffs)}}></input>{clickedEdit === false && <i className="bx bxs-edit text-gray-400 cursor-pointer absolute text-3xl flex float-right right-4 top-[30%]" onClick={() => {setEditingId(`role_${staffs.sid}`); setClickedEdit(true); handleEditStaff(staffs)}}/>}</div>
                                            </div>
                                        </div>

                                        <div className="flex flex-col">
                                            <p className="text-2xl font-semibold">Salary</p>
                                            <div className="flex relative"><input className="text-2xl w-full rounded-xl outline-none text-gray-900 font-bold p-4" type="text" key={`salary_${staffs.sid}`} value={editingId ? draft?.salary ?? staffs.salary : staffs.salary} name="salary" readOnly={!clickedEdit} onChange={(e) => handleStaffChange(e, staffs.sid)} onClick={() => {setEditingId(`role_${staffs.sid}`); setClickedEdit(true); handleEditStaff(staffs)}}></input>{clickedEdit === false && <i className="bx bxs-edit text-gray-400 cursor-pointer absolute text-3xl flex float-right right-4 top-[30%]" onClick={() => {setEditingId(`role_${staffs.sid}`); setClickedEdit(true); handleEditStaff(staffs);}}/>}</div>
                                        </div>
                                        <div className="flex flex-col">
                                            <p className="text-2xl font-semibold">Account Name</p>
                                            <input className="text-2xl bg-gray-300 rounded-xl outline-none border border-spacing-2 border-gray-300 text-gray-900 font-bold p-4" type="text" value={staffs.accountname} readOnly></input>
                                        </div>
                                        <div className="flex flex-col">
                                            <p className="text-2xl font-semibold">Account Number</p>
                                            <input className="text-2xl bg-gray-300 rounded-xl outline-none border border-spacing-2 border-gray-300 text-gray-900 font-bold p-4" type="text" value={staffs.accountnumber} readOnly></input>
                                        </div>
                                        <div className="flex flex-col">
                                            <p className="text-2xl font-semibold">Bank Name</p>
                                            <input className="text-2xl bg-gray-300 rounded-xl outline-none border border-spacing-2 border-gray-300 text-gray-900 font-bold p-4" type="text" value={staffs.bankname} readOnly></input>
                                        </div>
                                        <div className="flex flex-col">
                                            <p className="text-2xl font-semibold">Joined Date</p>
                                            <input className="text-2xl rounded-xl bg-transparent outline-none border border-spacing-2 border-gray-300 text-gray-900 font-bold p-4" type="text" value={staffs.created_at} readOnly></input>
                                        </div>
                                    </div>
                                );})}
                            </div>
                        </div>
                        {clickedEdit === true &&
                         <div className="sticky bottom-0 w-full flex flex-row gap-6">
                            <button className="flex bg-green-500 w-full justify-center p-6 rounded-xl text-center align-middle text-xl font-bold text-white shadow-[0px_0px_10px_rgba(41,43,47,0.5)]" onClick={handleSave}>Save</button>
                            <button className="flex bg-red-500 w-full justify-center p-6 rounded-xl text-center align-middle text-xl font-bold text-white shadow-[0px_0px_10px_rgba(41,43,47,0.5)]" onClick={handleCancel}>Cancel</button>
                        </div>
                        }
                        {clickedEdit === false && 
                        <div className="sticky bottom-0 w-full">
                            <button className="flex bg-gray-500 w-full justify-center p-6 rounded-xl text-center align-middle text-xl font-bold text-white shadow-[0px_0px_10px_rgba(41,43,47,0.5)]" onClick={() => setClickedEdit(true)}>Edit</button>
                        </div>
                        }
                    </div>
                )}

                {(selectedSIdeBAr === "requests") && (
                    <div>
                        <h1 className="text-5xl font-black mb-[40px]">Join Requests</h1>
                        <div>
                            {selectedCompany?.requests?.map((req) => (
                                <div>
                                    <div>
                                        <span className="rounded-[50%] p-8 w-4 h-4 bg-blue-400 text-white font-bold text-xl flex justify-center items-center">{req?.firstname?.charAt(0)}{req?.lastname?.charAt(0)}</span>
                                        <h1>{req?.firstname} {req?.lastname}</h1>
                                    </div>
                                    
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {(selectedCompany?.role === "Staff" && selectedSIdeBAr === "overview") && (
                <div className="flex gap-[2%] h-[70%]">
                    <div className="bg-[#070b17] relative flex-1 rounded-xl pay-roll">k</div>
                    <div className="bg-white w-[40%] rounded-xl"></div>
                </div>
                )}
            </div>
        </div>    
    );
}

export default Home;