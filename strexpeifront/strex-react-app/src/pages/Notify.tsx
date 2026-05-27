import axios from "axios";
import { useState, type HtmlHTMLAttributes, useEffect } from "react";
import { Route, useActionData, useNavigate } from 'react-router-dom';
import 'boxicons/css/boxicons.min.css';
import logo from '../assets/images/strexpei-logo.png';
import { useCompanyPage } from "../hooks/useCompany";
import type { Company } from "../schemas/CompanyTypes";
import type { User } from "../schemas/authTypes";
import { useUserPage } from "../hooks/useUser";
import { useUser } from "../context/userContext";
import api from "../api";
import "../assets/css/notify.css";
import type { Notifications, ListNotifications } from "../schemas/Notify";

export default function Notification () {
    
    const { currentUser, error, loading } = useUserPage();
    const [ clicked, setClicked ] = useState("");
    const [ isSelected, setIsSelected] = useState(false);
    const [ nerror, setError ] = useState('');
    const [ opened, setOpened ] = useState(false);
    // const [selectedCompany, setSelectedCompany] = useState<Notifications | null>(null);
    const [ notifys, setNotifys ] = useState<Notifications[]>([]);
    
    const navigate = useNavigate();
    
    const forNotify: Notifications[] = [
        ...(notifys?? []).map(r => ({
            nid: r.nid,
            title: r.title,
            message: r.message,
            timestamp: r.timestamp,
            isRead: r.isRead,
            sender_id: r.sender_id,
            receiver_id: r.receiver_id,
            // sender: User;
            // receiver: User;
        })),
    ]
    useEffect(() => {
        const fetchNotifications = async () => {
            const resp = await api.get<ListNotifications>('/users/notifications')
            setNotifys(resp.data.notifications);
            console.log(resp.data.notifications)
        };
        fetchNotifications();
        console.log(notifys);
    }, [currentUser]);

    type Incoming = { sender_nid: string; role: string; company_name: string; sender_name: string; token: string; status: string };

    
    console.log(currentUser);
    const forRequest: Incoming[] = [
        ...(currentUser?.companies ?? []).flatMap(r => 
        (r.request ?? []).map(req => ({
            sender_nid: req?.created_by,
            role: req?.position,
            company_name: r?.company_name,
            token: req?.token,
            sender_name: req?.creator?.firstname,
            status: req?.status
        }))),
    ]

    const handleAccept = async (token: string) => {
        try {
            await api.get(`/staffs/accept_request/${token}`)

        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err.response?.data.message || "Request not accepted");
            } else {
                setError("Server Not Reachable");
            }
        }
    }

    const handleDecline = async (token: string) => {
        try {
            await api.get(`/staffs/reject_request/${token}`)

        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err.response?.data.message || "Request not rejected");
            } else {
                setError("Server Not Reachable");
            }
        }
    }

    

    //Fetch on mount
    

    //Mark as read - updates local state + tells the API
    const markAsRead = async (nid: string) => {
        //Update UI
        setNotifys(prev => prev.map(n => n.nid === nid ? { ...n, isRead: true} : n))

        //Update backend
        try {
            await api.patch(`/users/notifications/${nid}/read`);
        } catch ( err: unknown ) {

            if (axios.isAxiosError(err)) {
                setError(err.response?.data.message || "Notification not updated")
            } else {
                setError("Server not reachable");
            }
            console.log(nerror);
        }
        
    }
    //users/notifications/{notification_id}/{read}



    return (
        <div className={"not-container"}>
            {forNotify?.map((request) => (
                <>
                    <div key={request.nid} onClick={() => {setClicked(request.nid); !request.isRead ? markAsRead(request.nid) : ""}} className={`${ request.isRead ? "clicked-not": "unclicked-not"}`} id="info-box">
                        <h3>{request.title}</h3>
                        <p className="mess">{request.message}</p>
                        <i className="bx bx-dots-vertical"/>
                    </div>
                    {forRequest?.map((notify) => {
                        if (notify.sender_nid == request.sender_id )
                            return  <div className={`${ clicked === request.nid ? "opened": "not-opened"}`}>
                                            <h3 className="title"><i className="bx bxs-chevron-left" onClick={() => {setClicked("");}}/>{request.title}</h3>
                                            <div className="message-box">
                                                <p className="mess">{request.message}</p>
                                                <div className="accdec">
                                                    <button className={` not-btn ${ notify.status === "accepted" || notify.status ===  "rejected" ? "accepted-btn": "accept-btn"}`} onClick={() => handleAccept(notify.token)} disabled={notify.status === "accepted" || notify.status === "rejected"}>Accept</button>
                                                    <button className={` not-btn2 ${ notify.status === "accepted" || notify.status ===  "rejected" ? "declined-btn": "decline-btn"}`} onClick={() => handleDecline(notify.token)} disabled={notify.status === "rejected" || notify.status === "accepted"}>Decline</button>
                                                </div>
                                            </div>
                                    </div>})
                    }
                </>
                ))}
        </div>
    );
}