import axios from "axios";
import { useState } from "react";
import { useNavigate } from 'react-router-dom'
import 'boxicons/css/boxicons.min.css';
import '../assets/css/main.css';
import '../assets/css/form.css';
import logo from '../assets/images/strexpei-logo.png'


function SignUp () {
    const [formData, setFormData] = useState({
        firstname: '',
        lastname: '',
        email: '',
        phone: '',
        password: ''
    });

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
            const response = await axios.post(
                `http://localhost:8000/api/v1.0/auths/sign_up`, formData
            );
            
            setMessage(response?.data?.message);
            console.log(response.data?.message);

            navigate('/verify-account', {state: { email: formData.email , password: formData.password, theotp: response?.data?.code }});

        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err.response?.data.message || "sign up failed");
            } else {
                setError('Server not reachable');
            }
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
            <div className="card">
                <div className="logo">
                    <img src={logo} alt="Logo" className="log"/>
                </div>
                <form onSubmit={handleSubmit}>
                <h1>Create your Strexpei Account</h1>
                <p className="subtitle">fill in with your details</p>

                <div className="input-group email-box">
                    
                    <i className="bx bx-user left-icon"/>
                    <input type="text" name="firstname" value={formData.firstname} onChange={handleChange} placeholder="firstname" maxLength={25} required/>
                </div>

                <div className="input-group email-box">
                    
                    <i className="bx bx-user left-icon"/>
                    <input type="text" name="lastname" value={formData.lastname} onChange={handleChange} placeholder="lastname" maxLength={25} required/>
                </div>

                <div className="input-group email-box">
                    
                    <i className="bx bx-envelope left-icon"/>
                    <input type="email" name="email" value={formData.email} onChange={handleChange} placeholder="you@example.com" maxLength={25} required/>
                </div>

                <div className="input-group email-box">
                    
                    <i className="bx bx-phone left-icon"/>
                    <input type="phone" name="phone" value={formData.phone} onChange={handleChange} placeholder="***********" maxLength={25} required/>
                </div>

                <div className="input-group">
                    <i className='bx bx-lock-alt left-icon'/>
                    <input type={showPassword ? "text" : "password"} name="password" value={formData.password} onChange={handleChange} placeholder="password" maxLength={15} minLength={6} required/>
                    <i
                        className={`bx ${showPassword ? "bx-hide" : "bx-show"} right-icon`}
                        onClick={() => setShowPassword(!showPassword)}
                    />
                </div>

                <button className="signup-btn" type="submit">Signup →</button>
                </form>
                <div className="divider">or continue with</div>

                <div className="socials">
                    <div className="social-btn"></div>
                    <div className="social-btn"></div>
                    <div className="social-btn fingerprint"></div>
                </div>

                <p className="signup">
                Do you have an account? <span onClick={() => navigate("/sign-in")}>Sign In</span>
                </p>
            </div>

            {message && <p style={{ color: "green" }}>{message}</p>}
            {error && <p style={{ color: "red" }}>{error}</p>}
        </div>
        </>
    );
}

export default SignUp;