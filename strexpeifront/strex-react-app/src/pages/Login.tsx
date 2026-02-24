import axios from "axios";
import { useState } from "react";
import { useNavigate } from 'react-router-dom'
import 'boxicons/css/boxicons.min.css';
import '../assets/css/main.css'

function Login () {
    const [formData, setFormData] = useState({
        email: '',
        password: ''
    });

    const [message, setMessage] = useState('');
    const [error, setError] = useState('')
    const navigate = useNavigate();

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setFormData({...formData,[name]: value});
    }

    const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault(); //prevents page reload

        try {
            const response = await axios.get(
                `http://localhost:8000/api/v1.0/auths/sign_in/${formData.email}/${formData.password}`
            );
            localStorage.setItem("access_token", response.data.access_token);
            localStorage.setItem("refresh_token", response.data.refresh_token);
            
            setMessage(response.data.detail);

            navigate("/Header");
        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err.response?.data.detail || "Login failed");
            } else {
                setError('Server not reachable');
            }
        }
    };

    console.log(localStorage.getItem("access_token"));

    return (
        <div className="container">
            
            <form onSubmit={handleSubmit} className="form-box">
                <h2>Login</h2>
                <div>
                    <input
                        type="email"
                        name="email"
                        placeholder="Email"
                        value={formData.email}
                        onChange={handleChange}
                        required
                    />
                    <i className="bx bxs-user"></i>
                </div>
                <br/>

                <div>
                    <input
                        type="password"
                        name="password"
                        placeholder="Password"
                        value={formData.password}
                        onChange={handleChange}
                        required
                    />
                    <i className="bx bxs-lock"></i>
                </div>
                <br/>
                <button type="submit">login</button>
            </form>

            {/* Display messages */}
            {message && <p style={{ color: "green" }}>{message}</p>}
            {error && <p style={{ color: "red" }}>{error}</p>}
        </div>
    )
}

export default Login;