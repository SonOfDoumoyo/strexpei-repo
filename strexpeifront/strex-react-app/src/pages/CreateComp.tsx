import { useState } from "react";
import api from "../api";
import { useNavigate } from "react-router-dom";
import type { ReactFormState } from "react-dom/client";
import { getCurrentUid } from "../hooks/currentUid";
import axios from "axios";

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
        } catch (err: unknown) {
            if (axios.isAxiosError(err)){
                setError(err.response?.data.detail || "Account creation failed!");
            } else {
                setError("Server not reachable");
            }
        }
    }


    return (
        <div className="bg-gray-200 h-full">
            <div className="p-6">
                <h1 className="text-5xl font-bold text-gray-700 mb-3">Create Your Company</h1>
                <p className="font-semibold text-3xl text-gray-500 mb-14">Set up your organisation on Strexpei to manage staff, automate payroll and securely distribute salaries in one place</p>
                <form onSubmit={handleSubmit} className="flex gap-4 flex-col">
                

                <div className="flex">
                    <input type="text" name="company_name" className="p-4 w-full outline-none" value={formData.company_name} onChange={handleChange} placeholder="Enter company name" maxLength={25} required/>
                </div>

                <div className="flex">
                    <input type="text" name="address"  className="p-4 w-full outline-none" value={formData.address} onChange={handleChange} placeholder="Enter company address" maxLength={50} required/>
                </div>

                <div className="flex">
                    <input type="text" name="position"  className="p-4 w-full outline-none" value={formData.position} onChange={handleChange} placeholder="Enter your postion" maxLength={50} required/>
                </div>


                <div className="flex gap-4">
                    <button className="p-7 bg-blue-400 rounded-xl w-[50%] text-white font-black" type="submit" onClick={() => navigate(`/home/${getCurrentUid()}`)}>Create</button>
                    <button className="p-7 border-[2.9px] border-red-600  rounded-xl w-[50%] font-black text-red-600 bg-red-400" onClick={() => navigate(`/home/${getCurrentUid()}`)}>Back</button>
                </div>
                </form>
            </div>

        </div>
    );
}

export default CreateCompany;