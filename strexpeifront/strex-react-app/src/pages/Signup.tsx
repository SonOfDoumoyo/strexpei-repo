import React, {useState} from "react";
import axios from 'axios';
import { useNavigate } from "react-router-dom";
import '../assets/css/main.css'
import '../assets/css/forms.css'

function SignUp() {
    const [formData, setFormData] = useState({
        firstname: "",
        lastname: "",
        email: "",
        phone: "",
        password: ""
    });

    const [message, setMessage] = useState("");
    const [error, setError] = useState("");

    const navigate = useNavigate(); // <-- hook to navigate

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const {name, value} = e.target;
        setFormData({ ...formData, [name]: value });
    };

    const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
        e.preventDefault();

        try {
            const respone = axios.post(
                "http://localhost:8000/api/v1.0/auths/sign_up",
                formData
            );
            setMessage((await respone).data.message)
            setError("")

             // navigate to dashboard after access
            navigate("/Home");
        } catch (err: unknown) {
            if (axios.isAxiosError(err)) {
                setError(err.response?.data?.detail || "Error creating account");
            } else {
                setError("Server not reachable");
            }
            setMessage("");
        }
    };


    return (
        <div className="signup">
            <h2>Sign Up</h2>
            <form onSubmit={handleSubmit} className="form">
                <input
                    type="text"
                    name="firstname"
                    placeholder="First Name"
                    value={formData.firstname}
                    onChange={handleChange}
                    maxLength={25}
                    required
                />
                <br />

                <input
                    type="text"
                    name="lastname"
                    placeholder="Last Name"
                    value={formData.lastname}
                    onChange={handleChange}
                    maxLength={25}
                    required
                />
                <br />

                <input
                    type="email"
                    name="email"
                    placeholder="Email"
                    value={formData.email}
                    onChange={handleChange}
                    required
                />
                <br />

                <input
                    type="text"
                    name="phone"
                    placeholder="Phone"
                    value={formData.phone}
                    onChange={handleChange}
                    maxLength={11}
                    required
                />
                <br />

                <input
                    type="password"
                    name="password"
                    placeholder="Password"
                    value={formData.password}
                    onChange={handleChange}
                    minLength={6}
                    maxLength={15}
                    required
                />
                <br />
                <button type="submit">Sign Up</button>
            </form>

            {message && <p style={{ color: "green" }}>{message}</p>}
            {error && <p style={{ color: "red" }}>{error}</p>}
        </div>
    );
}

export default SignUp;
