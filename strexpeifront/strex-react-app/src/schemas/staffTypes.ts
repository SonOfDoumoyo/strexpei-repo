import type { Company } from "./CompanyTypes";
import type { User } from "./authTypes";

export type Staff = {
    sid: string;
    company_id: string;
    user_id: string;
    firstname: string;
    lastname: string;
    salary: string;
    position: string;
    accountname: string;
    accountnumber: string;
    bankname: string;
    bankcode: string;
    pay_receipts: [];
    updated_at: string;
    created_at: string;
    company: Company;
    user: User[];
}