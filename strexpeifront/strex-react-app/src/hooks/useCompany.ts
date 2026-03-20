import { getCompany } from "../routes/companyRoutes";

export function useCompanyPage() {
    const { companies, error } = getCompany();

    return {
        companies: companies ?? [],
        error,
        loading: !error && !companies,
    };
}