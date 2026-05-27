import axios from "axios";
import { useState } from "react";
import { useNavigate } from 'react-router-dom'
import 'boxicons/css/boxicons.min.css';
import { useContext } from "react";
import api from "../api";
import { UserContext } from "../context/userContext";
import { setAccessToken } from "../hooks/useAuths";
import "../assets/css/login.css";
import { Link } from "react-router-dom";
import { getCurrentUid, setCurrentUid } from "../hooks/currentUid";


function Login () {
    const [formData, setFormData] = useState({
        email: '',
        password: '',
    });

    const [rememberMe, setRememberMe] = useState(false);

    const { setCurrentUser } = useContext(UserContext)!;

    const formKeys = ["email", "password"]

    const [message, setMessage] = useState('');
    const [error, setError] = useState('')
    const [showPassword, setShowPassword] = useState(false);
    const [ page, setPage ] = useState('email');
    const navigate = useNavigate();

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setFormData({...formData,[name]: value});
    }

    const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault(); //prevents page reload

        try {
            const response = await api.get(
                `/auths/sign_in/${formData.email}/${formData.password}/${rememberMe}`
            );
            setCurrentUid(response.data.user.user_id);
            setAccessToken(response.data.user.user_id, response.data.access_token)
   
            if (response?.data.code) {
                navigate(`/verify-account`, {state: {email: formData.email, password: formData.password, theotp: response?.data.code}})
            } else {
                setCurrentUser(response.data.user.user_details);
                navigate(`/home/${response.data.user.user_id}`);
            }
            
            
        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err.response?.data.message || "Login failed");
            } else {
                setError('Server not reachable');
            }
            setFormData(
                prev => ({ ...prev, password: ''})
            );
            setTimeout(() => setError(""), 8000);
        }
    };


    return (
        <>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <div className="bg-gray-50 min-h-screen">
                {(error) && (<div className="absolute top-0 right-0 border m-2 border-red-500 text-red-500 p-3">
                        <p id="error-msg">{error}</p>
                </div>)}
            
                <div className="min-h-screen flex">
                    <div className="flex-1 flex items-center justify-center p-8">
                        <div className="w-full max-w-xl">

                            {/* Mobile logo */}
                            <div className="flex items-center justify-center gap-3 mb-10">
                                <div className="text-3xl font-bold text-gray-900">Strex<span className="text-blue-600">Pei</span></div>
                            </div>

                            <div className="bg-white w-full rounded-3xl shadow-xl p-10">
                                <h2 className="text-3xl font-bold text-gray-900 mb-2">Welcome back</h2>
                                <p className="text-gray-600 mb-8">Sign in to manage your payroll</p>
                            

                                <form onSubmit={handleSubmit} className="space-y-6">

                                    {/* email */}
                                    <div>  
                                        <label className="block text-base font-medium text-gray-700 mb-2">Email Address</label>
                                        <div className="relative">
                                            <div className="absolute flex left-4 self-center text-gray-400">
                                                <i className="bx bxs-envelope"/>
                                            </div>
                                            <input className="w-full pl-11 pr-4 py-4 border text-gray-900 border-gray-300 rounded-2xl focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" type="email" name="email" value={formData.email} onChange={handleChange} maxLength={25} required/>
                                        </div>    
                                    </div>

                                    {/* password */}
                                    <div>
                                        <label className="block text-base font-medium text-gray-700 mb-2">Password</label>
                                        <div className="relative">
                                            <div className="absolute left-4 flex self-center text-gray-400">
                                                <i className="bx bxs-lock"/>
                                            </div>
                                            <input className="w-full pl-11 pr-4 py-4 border text-gray-900 border-gray-300 rounded-2xl focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" type={showPassword ? "text" : "password"} name="password" value={formData.password} onChange={handleChange} maxLength={15} minLength={6} required></input>
                                            <div className="absolute right-4 inline-flex items-center text-center pt-1 justify-center self-center text-gray-400 hover:text-gray-600">
                                                <i
                                                    className={`bx ${showPassword ? "bxs-hide" : "bxs-show"}`}
                                                    onMouseDown={() => setShowPassword(true)}
                                                    onMouseUp={() => setShowPassword(false)}
                                                />
                                            </div>
                                        </div>   
                                    </div>

                                    {/* remeber mw + forgot password */}
                                    <div className="flex items-center justify-between">
                                        <label className="flex items-center gap-2 text-base">
                                            <input type="checkbox" className="w-4 h-4 accent-blue-600" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)}/>
                                            <span className="text-gray-600">Remeber me</span>
                                        </label>
                                        <a href="#" className="text-base text-blue-600 hover:underline">Forgot Password?</a>
                                    </div>
                                    
                                    {/* Login button */}
                                    <button className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 rounded-2xl tansistion duration-300 text-lg" type="submit">Sign In</button>
                                </form>

                                {/*  Divider */}
                                <div className="my-8 flex items-center gap-4">
                                    <div className="flex-1 h-px bg-gray-200"></div>
                                    <span className="text-gray-400 text-base">OR</span>
                                    <div className="flex-1 h-px bg-gray-200"></div>
                                </div>

                                {/* Google sign in */}
                                <button className="w-full border border-gray-300 hover:border-gray-400 py-4 rounded-2xl flex items-center justify-center gap-3 font-medium transition text-gray-900">
                                    Continue with Google
                                </button>

                                {/* Sign up-link */}
                                <p className="text-center mt-8 text-gray-600">
                                    Don’t have a Strexpei Account yet?
                                    <Link to="/sign-up" className="text-blue-700 font-semibold hover:underline ml-1">Click here to get one</Link>
                                </p>   
                            </div>

                            {/* Footer note  */}
                            <p className="text-center text-sm text-gray-500 mt-8">
                                Secure login powered by Strexpei . &copy; 2026
                            </p>
                        </div>
                    </div> 
                </div>

            </div>
        </>
    );
}

export default Login;