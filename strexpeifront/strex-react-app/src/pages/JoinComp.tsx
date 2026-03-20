import api from "../api";
import axios, { Axios, AxiosError } from "axios";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import logo from "../assets/images/strexpei-logo.png"
import "../assets/css/main.css";

function JoinCompany () {

    const [formData, setFormData] = useState({
        company_name: '',
        company_id: '',
        position: '',
        company_email: '',
    });
    const [error, setError] = useState("");
    const navigate = useNavigate();

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setFormData({...formData,[name]: value});
    }

    const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault();

        try {
            const response = await api.post('/staffs/join_request_company', formData);
            navigate("/Home");

        }catch (err: unknown) {
            if(axios.isAxiosError(err)) {
                setError(err.response?.data.message || "Request wasn't successful");
            } else {
                setError("Server not reachable");
            }
            console.log(error);
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
                <h1>Join Your Company</h1>
                <p className="subtitle">Request access to your company's workspace to start receiving payments and managing your staff account</p>

                <div className="input-group companyname-box">
                    
                    <i className="bx bxs-buildings left-icon"/>
                    <input type="text" name="company_name" value={formData.company_name} onChange={handleChange} placeholder="Enter company name" maxLength={25} required/>
                </div>

                <div className="input-group address-box">
                    
                    <i className="bx bxs-id-card left-icon"/>
                    <input type="text" name="company_id" value={formData.company_id} onChange={handleChange} placeholder="Enter company id" maxLength={50} required/>
                </div>

                <div className="input-group position-box">
                    
                    <i className="bx bxs-id-card left-icon"/>
                    <input type="text" name="position" value={formData.position} onChange={handleChange} placeholder="Enter your postion" maxLength={10} required/>
                </div>

                <div className="input-group email-box">
                    
                    <i className="bx bx-envelope left-icon"/>
                    <input type="email" name="company_email" value={formData.company_email} onChange={handleChange} placeholder="Enter company email" maxLength={25} required/>
                </div>


                <button className="signup-btn" type="submit">Join</button>
                </form>

                <p className="signup">
                Have a company? <span>Create company</span>
                </p>
            </div>

        </div>
        </>
    );
}

export default JoinCompany;