import React, { useEffect, useState } from "react";
import "../assets/css/profile.css";
import { useUserPage } from "../hooks/useUser";
import api from "../api";
import axios from "axios";
import { useContext } from "react";
import { useUser } from "../context/userContext";

export default function Profile() {
    const { currentUser, error, loading } = useUserPage();
    const { fetchUser } = useUser();

    const [ profdata, setProfData ] = useState({
        firstname: `${currentUser?.firstname}`,
        lastname: `${currentUser?.lastname}`,
        email: `${currentUser?.email}`,
        phone: `${currentUser?.phone}`,
    })
    const [ image, setImage ] = useState<string | null>(null)
    
    const [ edit, setEdit ] = useState(false);

    useEffect (() => {
        if (currentUser) {

            setProfData({
                firstname: `${currentUser?.firstname}`,
                lastname: `${currentUser?.lastname}`,
                email: `${currentUser?.email}`,
                phone: `${currentUser?.phone}`,
            });
        }
    }, [currentUser]);

    const handleProfilePicChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();

        const file = e.target.files?.[0];

        if (file) {
            const url = URL.createObjectURL(file);
            setImage(url);
        }
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setProfData({...profdata, [name]: value})
    }

    const handleEdit = async (e: React.SyntheticEvent<HTMLButtonElement>) => {
        e.preventDefault();

        try{
            const response = await api.patch(`/users/edit_details`, profdata)
        }catch (err: unknown){
            if (axios.isAxiosError(err)){
                console.log("hi");
            }
        } finally {
            setEdit(false);
            await fetchUser();
        }
    }


    return (
        <div className="profile-page">
            <div className="prof-body">
                <div className="display-profile">
                    <div className="pic-circle" style={{
                        backgroundImage: `url(${image})`,
                        backgroundPosition: "center",
                        backgroundSize: "cover",
                        }}>
                    </div>

                    <h3 className="user-name">{currentUser?.firstname} {currentUser?.lastname}</h3>
                    <h1>{currentUser?.email}</h1>
                    
                    <button className="edit-btn" onClick={() => setEdit(!edit)}>Edit profile</button>
                </div>
                <div className="display-info">
                    <h5 className="p-firstname">Firstname  {(edit == true) && (<input name="firstname" className="first-nam" type="text" maxLength={15} minLength={1} value={profdata.firstname}  onChange={handleChange}/>)} {(edit == false) && (<p>{currentUser?.firstname}</p>)}</h5>
                    <h5 className="p-lastname">Lastname {(edit == true) && (<input name="lastname" className="last-nam" type="text" maxLength={15} minLength={1}  value={profdata.lastname}  onChange={handleChange}/>)} {(edit == false) && (<p >{currentUser?.lastname}</p>)}</h5>
                    <h5 className="p-email">Email {(edit == true) && (<input name="email" className="user-email" type="email" value={profdata.email}  onChange={handleChange}/>)} {(edit == false) && (<p >{currentUser?.email}</p>)}</h5>
                    <h5 className="p-phone">Phone {(edit == true) && (<input name="phone" className="user-phone" type="phone" value={profdata.phone}  onChange={handleChange}/>)} {(edit == false) && (<p >{currentUser?.phone}</p>)}</h5>

                    {(edit == true) && (<button onClick={handleEdit} className="save-btn">Save changes</button>)}
                </div>
            </div>
            
        </div>
    )
}