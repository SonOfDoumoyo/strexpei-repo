import { useState } from "react";
import api from "../api";
import { useNavigate } from "react-router-dom";
import type { ReactFormState } from "react-dom/client";
import axios from "axios";
import '../assets/css/main.css';
import logo from "../assets/images/strexpei-logo.png";

function CreateCompany () {

    const [formData, setFormData] = useState({
        company_name: '',
        address: '',
        position: '',
    });
    const [error, setError] = useState("");

    const navigate = useNavigate();
    
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setFormData({...formData,[name]: value});
    }

    const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault();

        try{
            const response = await api.post(
                "/company/create_company", formData
            );
            navigate("/Home");
        } catch (err: unknown) {
            if (axios.isAxiosError(err)){
                setError(err.response?.data.detail || "Account creation failed!");
            } else {
                setError("Server not reachable");
            }
        }
    }


    return (
        <>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <div className="screen">
            <div className="card">
                <div className="logo">
                    <img src={logo} alt="Logo" className="log"/>
                </div>
                <form onSubmit={handleSubmit}>
                <h1>Create Your Company</h1>
                <p className="subtitle">Set up your organisation on Strexpei to manage staff, automate payroll and securely distribute salaries in one place</p>

                <div className="input-group companyname-box">
                    
                    <i className="bx bxs-buildings left-icon"/>
                    <input type="text" name="company_name" value={formData.company_name} onChange={handleChange} placeholder="Enter company name" maxLength={25} required/>
                </div>

                <div className="input-group address-box">
                    
                    <i className="bx bxs-map left-icon"/>
                    <input type="text" name="address" value={formData.address} onChange={handleChange} placeholder="Enter company address" maxLength={50} required/>
                </div>

                <div className="input-group position-box">
                    
                    <i className="bx bxs-id-card left-icon"/>
                    <input type="text" name="position" value={formData.position} onChange={handleChange} placeholder="Enter your postion" maxLength={10} required/>
                </div>


                <button className="signup-btn" type="submit">Create</button>
                </form>

                <p className="signup">
                Are you a staff member of an existing company? <span>Join company</span>
                </p>
            </div>

        </div>
        </>
    );
}

export default CreateCompany;