import type { User } from "./authTypes"
import type { Company } from "./CompanyTypes";

export type Request = {
    request_id: string;
    company_id: string;
    company_name: string;
    position: string;
    email: string;
    status: string;
    token: string;
    expires_at: string;
    revoked: boolean;
    revoked_at?: string | null;
    created_at: string;
    created_by: string;
    creator: User;
    company: Company;
}