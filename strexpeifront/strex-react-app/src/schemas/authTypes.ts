import type { Company } from "./CompanyTypes";
import type { Staff } from "./staffTypes";
import type { Request } from "./RequestTypes";
import type { Notifications } from "./Notify";

export type User = {
    uid: string;
    email: string;
    firstname: string;
    lastname: string;
    phone: string;
    password: string;
    verified: boolean;
    status: string;
    role: string;
    updated_at: string;
    created_at: string;
    deleted_at?: string | null;
    purge_at?: string | null;
    companies: Company[];
    staffs: Staff[];
    request: Request[];
    sent: Notifications[];
    received: Notifications[];
};