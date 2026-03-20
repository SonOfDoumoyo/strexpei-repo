import type { Staff } from "./staffTypes";
import type { Request } from "./RequestTypes";

export type Company = {
    cid: string;
    manager_id: string
    company_name: string;
    address: string;
    position: string;
    updated_at: string;
    is_deleted: boolean;
    deleted_at?: string | null;
    purge_at?: string | null;
    created_at: string;
    staffs: Staff[];
    request: Request[];
};

export type ResponseCompanyModel = {
    company: Company[];
}