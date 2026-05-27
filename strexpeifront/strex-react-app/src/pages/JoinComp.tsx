import api from "../api";
import axios, { Axios, AxiosError } from "axios";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../assets/css/joincreate.css";
import { getCurrentUid } from "../hooks/currentUid";


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
        <div className="bg-gray-200 h-full">
            <div className="p-6">
                    
                    <h1 className="text-5xl font-bold text-gray-700 mb-3">Join Your Company</h1>
                    <p className="font-semibold text-3xl text-gray-500 mb-14">Already part of an organisation? Request access to join your company workspace and start receiving payments through Strexpei.</p>

                    <form onSubmit={handleSubmit} className="text-xl flex flex-col gap-4">
                        <div className="flex w-full gap-4">
                            <div className="w-full">
                                <input type="text" className="p-4 w-full outline-none" name="company_name" value={formData.company_name} onChange={handleChange} placeholder="company name" maxLength={25} required/>
                            </div>

                            <div className="w-full">
                                <input type="text" className="p-4 w-full outline-none" name="company_id" value={formData.company_id} onChange={handleChange} placeholder="Enter company id" maxLength={50} required/>
                            </div>
                        </div>

                        <div className="flex w-full gap-4">
                            <div className="w-full">
                                <input type="text" className="p-4 w-full outline-none" name="position" value={formData.position} onChange={handleChange} placeholder="Enter your postion" maxLength={10} required/>
                            </div>

                            <div className="w-full">
                                <input type="email" className="p-4 w-full outline-none" name="company_email" value={formData.company_email} onChange={handleChange} placeholder="Enter company email" maxLength={25} required/>
                            </div>
                        </div>
                        <div>
                            <textarea name="" placeholder="Message" id="" className="w-full p-4 min-h-44 outline-none"></textarea>
                        </div>
                        <div className="flex gap-4">
                            <button className="p-7 bg-blue-400 rounded-xl w-[50%] text-white font-black" type="submit" onClick={() => navigate(`/home/${getCurrentUid()}`)}>Join</button>
                            <button className="p-7 border-[2.9px] border-red-600  rounded-xl w-[50%] font-black text-red-600" onClick={() => navigate(`/home/${getCurrentUid()}`)}>Back</button>
                        </div>
                    </form>

            </div>
        </div>
    );
}

export default JoinCompany;