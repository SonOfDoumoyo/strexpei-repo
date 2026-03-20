import logo from "../assets/images/strexpei-logo.png"
import "../assets/css/main.css";
import '../assets/css/verify.css';
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api from "../api";
import axios from "axios";
import { setUser } from "../context/userContext";
import { setAccessToken } from "../hooks/useAuths";
import { ResendCountdown } from "./coundowner";

function  VerifyAccount() {

    const [ otp, setOtp ] = useState("");
    const [ otpCorrect, setIsOtpCorrect ] = useState(false);
    const [ otpWrong, setOtpWrong ] = useState(false);
    const [ maxAttemptsReached, setMaxAttempts ] = useState(false);

    const [ text, setText ] = useState("");

    const [ cooldown, setCooldown ] = useState(30); //seconds
    const [ canResend, setCanResend ] = useState(true);
    const [showError, setShowError] = useState(false);

    const location = useLocation();
    //copy the route state info into the local useState
    const [ theotp, setTheOtp ] = useState(location.state?.theotp)

    
    //Counter timer 
    useEffect(() => {
        if (cooldown <= 0) {
            setCanResend(true);
            return;
        }
        const timer = setTimeout(() => setCooldown(c => c - 1), 1000)
        return () => clearTimeout(timer);
    }, [cooldown]);

    const [formData, setFormData] = useState({
        code1: '',
        code2: '',
        code3: '',
        code4: '',
        code5: '',
        code6: '',
    });

    const inputs = useRef<(HTMLInputElement | null)[]>([]);
    const otpKeys = ["code1", "code2", "code3", "code4", "code5", "code6"];

    const navigate = useNavigate();
    const [error, setError ] = useState('');
    const { state } = useLocation();
    const { email, password } = state || {};

    interface ResendCountdownProps {
        onCountdownEnd: () => void;
    }


    const handleChange = ( e: React.ChangeEvent<HTMLInputElement>, index: number ) => {
        const value = e.target.value;

        if (!/^\d$/.test(value)) return;

        // Update formData with the key name
        setFormData(prev => ({ ...prev, [otpKeys[index]]: value }));

        // Move to next input 
        if (index < 5) {
            inputs.current[index + 1]?.focus();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, index: number ) => {
        if (e.key === "Backspace" && !e.currentTarget.value && index > 0) {
            //Clear previous input in form data
            setFormData(prev => ({ ...prev, [otpKeys[index - 1]]: ""}));
            inputs.current[index - 1]?.focus();
        } else if (e.key === "Backspace") {
            setFormData(prev => ({ ...prev, [otpKeys[index]]: ""}))
        }
    };

    const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault();
        setError("");
        setText("");
        try {
            const codes = otpKeys.map(key => formData[key as keyof typeof formData]).join("");

            const otpVerifyResp = await api.post(`/auths/verify/${ email }/${ codes }`);
            const response = await api.get(`/auths/sign_in/${ email }/${ password }`);

            setAccessToken(response?.data.access_token)
            setUser(response?.data.user);

            
            setIsOtpCorrect(true);
            setOtpWrong(false);
            navigate('/workspace');

            
                    
        } catch (err: unknown){
            
            if (axios.isAxiosError(err)){
                const message = err.response?.data?.message || "Verification failed";
                setError(message);
            } else {
                setError("Server not reachable");
            }
            setFormData(
                Object.fromEntries(otpKeys.map((key) => [key, ""])) as typeof formData
            )
            setTimeout(() => setError(""), 5000);
        }
    }

    const handleResend = async (e: React.MouseEvent<HTMLSpanElement>) => {
        e.preventDefault();

        try {
            const resp = await api.post(
                `/auths/otp_resend/${email}`
            )
            const data = resp.data
            console.log(data);

            if (data?.allowed === false && data?.message?.seconds) {

                setCooldown(data?.message?.seconds);
                setCanResend(false);

            } else if (data?.allowed === false && data?.message === "Max resend attempts reached. Try again later") {
                setError(data?.message)
                setMaxAttempts(true);

                setTimeout(() => setShowError(false), 5000);


            } else if (data?.code && data?.success === true){

                setTheOtp(data?.code);
                setCanResend(false);
                setMaxAttempts(false);
                setCooldown(60);

            } else if (data?.allowed == false && !data?.message?.seconds) {

                setError(data?.message);
                console.log(text);
                setMaxAttempts(true);

                setTimeout(() => setError(""), 5000);
            }

        }catch (err: unknown){

            if (axios.isAxiosError(err)){
                setError(err.response?.data?.message || "Otp not sent")
            } else {
                setError("Server not reachable")
            }
            setTimeout(() => setError(""), 5000);
        }
    }

    return (
        <>
        <div className="screen work-screen">
            <div className='card work-card'>
                <img src={logo} alt="Logo" className="log"/>

                   
                <div className='logo-box'>
                    <h1>Verify Your Strexpei Account</h1>
                </div>

                {(error) && (<div className="error-box">
                    <p id="error-msg">{error}</p>
                </div>)}
                
                <div className="otp-message">
                    <p>We've sent a verification code to your email. </p>
                    <p> Enter the code below to activate your account and continue</p>
                </div>
                <form onSubmit={handleSubmit} className="vform-box">
             

                <div className="verify-box input-group">
                    <div className={`${otpCorrect ? "otp-correct": otpWrong ? "all-red":"otp-boxes"}`}>
                        {otpKeys.map((key, index) => (
                            <input 
                                className="input-otp"
                                key={key}
                                ref={ (el) => { if (el) inputs.current[index] = el}}
                                value={formData[key as keyof typeof formData]}
                                maxLength={1}
                                onChange={(e) => handleChange(e, index)}
                                onKeyDown={(e) => handleKeyDown(e, index)}
                            />    
                        ))}
                    </div>

                    <div className="btn-div">
                        <button className="manager-btn verify-btn" type="submit" disabled={!otpKeys.every(key => formData[key as keyof typeof formData])}>Verify</button>
                    </div>
                </div>
                </form>
                {(maxAttemptsReached === true ) && (
                    <ResendCountdown onCountdownEnd={() => setMaxAttempts(false)}/>
                )}
                { (maxAttemptsReached === false ) && (
                <p className="signup resend-otp">Didn't receive a code?<span className="otp-re" onClick={handleResend}>{canResend ? "Resend OTP" : `Resend in ${cooldown}s`}</span></p>
                )}
            </div>
          </div>  
        </>
    );
}

export default VerifyAccount;