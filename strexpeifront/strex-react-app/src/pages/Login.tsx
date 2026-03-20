import axios from "axios";
import { useState } from "react";
import { useNavigate } from 'react-router-dom'
import 'boxicons/css/boxicons.min.css';
import '../assets/css/main.css';
import '../assets/css/form.css';
import '../assets/css/verify.css';
import logo from '../assets/images/strexpei-logo.png'
import api from "../api";
import { setAccessToken } from "../hooks/useAuths";
import { setUser, getUser } from "../context/userContext";


function Login () {
    const [formData, setFormData] = useState({
        email: '',
        password: ''
    });

    const formKeys = ["email", "password"]

    const [message, setMessage] = useState('');
    const [error, setError] = useState('')
    const [showPassword, setShowPassword] = useState(false);
    const navigate = useNavigate();

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setFormData({...formData,[name]: value});
    }


    const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault(); //prevents page reload

        try {
            const response = await api.get(
                `/auths/sign_in/${formData.email}/${formData.password}`
            );
            setAccessToken(response.data.access_token)
            setUser(response.data.user);

            navigate("/Home");
        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err.response?.data.message || "Login failed");
            } else {
                setError('Server not reachable');
            }
            setFormData(
                prev => ({ ...prev, password: ''})
            );
            setTimeout(() => setError(""), 5000);
        }
    };


    return (
        <>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <div className="screen">
            {(error) && (<div className="error-box log-error">
                    <p id="error-msg">{error}</p>
            </div>)}
            <div className="login-logo">
                    <img src={logo} alt="Logo" className="log"/>
                    <h1>trexpei</h1>
            </div>
            <div className="card">
                
                
                <form onSubmit={handleSubmit}>
                <h1>Welcome to Strexpei</h1>
                <p className="subtitle">Sign in to continue</p>

                <div className="input-group email-box">
                    
                    <i className="bx bx-envelope left-icon"/>
                    <input type="email" name="email" value={formData.email} onChange={handleChange} placeholder="you@example.com" maxLength={25} required/>
                </div>

                <div className="input-group">
                    <i className='bx bx-lock-alt left-icon'/>
                    <input type={showPassword ? "text" : "password"} name="password" value={formData.password} onChange={handleChange} placeholder="password" maxLength={15} minLength={6} required/>
                    <i
                        className={`bx ${showPassword ? "bx-hide" : "bx-show"} right-icon`}
                        onClick={() => setShowPassword(!showPassword)}
                    />
                </div>

                <a href="#" className="forgot">Forgot Password?</a>

                <button className="login-btn" type="submit">Login →</button>
                </form>
                <div className="divider">or continue with</div>

                <div className="socials">
                    <div className="social-btn"></div>
                    <div className="social-btn"></div>
                    <div className="social-btn fingerprint"></div>
                </div>

                <p className="signup">
                Don’t have an account? <span onClick={() => navigate("/sign-up")}>Sign Up</span>
                </p>
            </div>

        </div>
        </>
    );
}

export default Login;