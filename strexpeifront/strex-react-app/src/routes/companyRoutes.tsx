import axios from "axios";
import { useState, useEffect } from "react";
import { useNavigate } from 'react-router-dom'
import 'boxicons/css/boxicons.min.css';
import '../assets/css/main.css';
import '../assets/css/form.css';
import api from "../api";
import { setAccessToken } from "../hooks/useAuths";
import { setUser, getUser } from "../context/userContext";
import type { Company, ResponseCompanyModel } from "../schemas/CompanyTypes";


export function getCompany(){

    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [companies, setCompanies] = useState<Company[]>([]);
    const user_id = getUser()?.user_id;

    useEffect(() => {
        if (!user_id) return;
        let cancelled = false;

        async function fetchCompany() {
            try {
                const response = await api.get<ResponseCompanyModel>(
                    `/company/get_user_company/${getUser()?.user_id}`
                );
                if (!cancelled) setCompanies(response.data.company);

            } catch (err: unknown) {
                if (cancelled) return;
                if (axios.isAxiosError(err)) {
                    setError(err.response?.data.detail || "Failed to fetch companies");
                } else {
                    setError('Server not reachable');
                }
            }
        }

        fetchCompany();

        return () => {
            cancelled = true;
        };

    }, []);

    return { companies, error }
}
