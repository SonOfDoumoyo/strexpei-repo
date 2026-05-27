import "../assets/css/worksp.css";
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import api from '../api';
import { useEffect, useState } from "react";
import { getCurrentUid } from "../hooks/currentUid";



function JoinCreate () {
    const navigate = useNavigate();
    const [ page, setPage ] = useState("null");
    const location = useLocation();

    useEffect(() => {
        if (location.pathname.startsWith("/workspace")) {
            setPage("null");
        }
        else if (location.pathname.endsWith("/create-company/:uid")) {
            setPage("notnull");
        }

        else if (location.pathname.endsWith("/join-company/:uid")) {
            setPage("notnull");
        }
    }, [location.pathname])

    const handleCreateClick = () => {
        setPage("notnull");
        navigate(`create-company/${getCurrentUid()}`);
    }

    const handleJoinClick = () => {
        setPage("notnull");
        navigate(`join-company/${getCurrentUid()}`);
    }

    const handleLogout = async () => {
        try {
            await api.post('/auths/logout')
        } catch (err) {}
        finally {
            navigate('/sign-in', {replace: true})
        }
    }

    return (
          <div className="work-screen">

            <div className="workspace-nav">
                <nav>
                    <h3>Strex<span>Pei</span></h3>
                    <button className='manager-btn exit-btn' onClick={handleLogout}>Logout</button>
                </nav>
            </div>
            {(page === "null") && (<div className='work-card'>
                <div className='join-box'>
                    <h1>Join or Create an organisation</h1>
                </div>

                <div className='join-create'>
                    <button className='manager-btn join-btn' onClick={handleJoinClick}>Join Organization</button>
                    <button className='manager-btn create-btn' onClick={handleCreateClick}>Create Organisation</button>
                </div>
                
            </div>)}
            <main>
                <Outlet/>
            </main>
          </div>  
    );
}

export default JoinCreate;