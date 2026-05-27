import "../assets/css/apppage.css";
import { Link } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import dashboardimg from "../assets/images/public-image.png";

export default function AppPage() {

    const navigate = useNavigate();

    return (
        <div className="text-gray-800 flex flex-col h-screen outline-none">
            {/* Navbar */}
            <nav className="bg-white border-b sticky top-0 z-50">
                <div className="mx-auto px-6 py-5 flex items-center justify-between">
                    <div>
                        <div className="text-2xl font-bold text-gray-900">Strex<span className="text-blue-600">Pei</span></div>
                    </div>

                    <div className="hidden md:flex items-center gap-8 text-gray-600 font-medium">
                        <Link className="nav-link" to="">Feature</Link>
                        <Link className="nav-link" to="">How it Works</Link>
                        <Link className="nav-link" to="">Pricing</Link>
                        <Link className="nav-link" to="">For Startups</Link>
                    </div>

                    <div className="flex items-center gap-4">
                        <Link className="text-gray-700 font-medium hover:text-gray-900 transition" to="/sign-in">Login</Link>
                        <button className="cta-btn bg-blue-600 text-white font-semibold px-7 py-3 rounded-2xl hover:bg-blue-700">Get Started Free</button>
                    </div>
                </div>
            </nav>

            {/* Hero Section */}
            <main className="overflow-y-auto">
                <section className="hero-bg text-white pt-24 pb-20">
                    <div className=" mx-auto px-6">
                        <div className="grid md:grid-cols-2 gap-12 items-center">
                            <div className="space-y-8">
                                <div className="inline-flex items-center gap-2 bg-white/20 backdrop-blur-md px-5 py-2 rounded-full text-sm font-medium">
                                    <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                                    Now available across Nigeria
                                </div>

                                <h1 className="text-5xl md:text-6xl font-bold leading-tight">
                                    Payroll that actually feels <span className="text-blue-200">simple</span>
                                </h1>

                                <p className="text-xl text-blue-100 max-w-lg">
                                    Create workspaces, onboard staff, and pay your entire team sucurely in one click.
                                    Built for Nigerian businesses - from startups to growing enterprises.
                                </p>

                                <div className="flex flex-col sm:flex-row gap-4">
                                    <Link to="" className="cta-btn bg-white text-blue-700 font-semibold px-10 py-4 rounded-2xl text-lg inline-flex items-center text-center justify-center gap-3 shadow-lg">
                                        <p>Start Free - No card needed</p>
                                        <i className="bx bxs-chevron-right"></i>
                                    </Link>
                                    <Link to="" className="cta-btn border-2 border-white/80 hover:bg-white/10 font-semibold px-8 py-4 rounded-2xl text-lg inline-flex items-center justify-center gap-2">
                                        <i className="bx bx-play-circle"></i> Watch 90-sec demo 
                                    </Link>
                                </div>

                                <div className="flex items-center gap-8 text-base pt-6">
                                    <div className="flex items-center gap-2">
                                        <i className="bx bx-check text-green-400"></i>
                                        <span>Free for teams under 10</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <i className="bx bx-check text-green-400"></i>
                                        <span>Instant payouts via Paystack & Flutterwave</span>
                                    </div>
                                </div>
                            </div>

                            {/* Hero visual */}
                            <div className="relative">
                                <div className="bg-white/10 backdrop-blur-lg rounded-3xl p-3 shadow-2xl border border-white/20">
                                    <img src={dashboardimg} alt="Strexpei Dashboard" className="rounded-2xl shadow-xl w-full"/>
                                </div>
                                {/* Floating badges */}
                                <div className="absolute -top-6 -right-6 bg-white text-gray-900 px-6 py-3 rounded-2xl shadow-xl flex items-center gap-3">
                                    <div className="text-3xl">💰</div>
                                    <div>
                                        <p>N24.8M</p>
                                        <p>paid this month</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Trust bar */}
                <section className="py-10 bg-white border-b">
                    <div className="max-w-7xl mx-auto px-6">
                        <p className="text-center text-gray-500 mb-6 text-base font-medium">Trusted by fast-growing Nigerian companies</p>
                        <div className="flex flex-wrap justify-center items-center gap-x-16 gap-y-8 opacity-75 grayscale">
                            <div className="text-3xl font-bold text-gray-400">Paystack</div>
                            <div className="text-3xl font-bold text-gray-400">Flutterwave</div> 
                            <div className="text-3xl font-bold text-gray-400">Moniepoint</div> 
                            <div className="text-3xl font-bold text-gray-400">Kuda</div> 
                            <div className="text-3xl font-bold text-gray-400">Opay</div>                    
                        </div>
                    </div>
                </section>


                {/* Problem Section */}
                <section className="py-24 bg-gray-50">
                    <div className="max-w-4xl mx-auto px-6 text-center">
                        <h2 className="text-4xl md:text-5xl font-bold mb-6 text-gray-900">
                            Stop wasting time on payroll every month
                        </h2>
                        <p className="text-xl text-gray-600">
                            Manual transfers, spreadsheets, missing payslips, and delayed payments are killing your productivity - and frustrating your team.
                        </p>
                    </div>
                </section>


                {/* Features */}
                <section className="py-24 bg-white">
                    <div className="max-w-7xl mx-auto px-6">
                        <h2 className="text-4xl font-bold text-center mb-16">Everything you need in one platform</h2>

                        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
                            <div className="feature-card bg-white border border-gray-100 p-8 rounded-3xl">
                                <div className="w-14 h-14 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center text-4xl mb-6">👥</div>
                                <h3 className="text-2xl font-semibold mb-3">Smart Onboarding</h3>
                                <p className="text-gray-600 leading-relaxed">Invite employees via email or phone. They accept and complete their profile in minutes.</p>
                            </div>

                            <div className="feature-card bg-white border border-gray-100 p-8 rounded-3xl">
                                <div className="w-14 h-14 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center text-4xl mb-6">⚡️</div>
                                <h3 className="text-2xl font-semibold mb-3">One-click bulk payroll</h3>
                                <p className="text-gray-600 leading-relaxed">Pay your entire team in a single secure checkout. Supports bulk salary, bonuses & allowances.</p>
                            </div>

                            <div className="feature-card bg-white border border-gray-100 p-8 rounded-3xl">
                                <div className="w-14 h-14 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center text-4xl mb-6">📱</div>
                                <h3 className="text-2xl font-semibold mb-3">Employee Self-Service</h3>
                                <p className="text-gray-600 leading-relaxed">Staff can view payslips, download tax documents, and track payment history anytime</p>
                            </div>

                            <div className="feature-card bg-white border border-gray-100 p-8 rounded-3xl">
                                <div className="w-14 h-14 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center text-4xl mb-6">🔁</div>
                                <h3 className="text-2xl font-semibold mb-3">Recurring Payroll</h3>
                                <p className="text-gray-600 leading-relaxed">Set it once and let automation handle monthly payments with full compliance</p>
                            </div>

                            <div className="feature-card bg-white border border-gray-100 p-8 rounded-3xl">
                                <div className="w-14 h-14 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center text-4xl mb-6">📊</div>
                                <h3 className="text-2xl font-semibold mb-3">Reports & Compliance</h3>
                                <p className="text-gray-600 leading-relaxed">Generate payslips, NHF, pension, and tax reports with one click.</p>
                            </div>

                            <div className="feature-card bg-white border border-gray-100 p-8 rounded-3xl">
                                <div className="w-14 h-14 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center text-4xl mb-6">🔒</div>
                                <h3 className="text-2xl font-semibold mb-3">Bank-Level Security</h3>
                                <p className="text-gray-600 leading-relaxed">256-bit encryption, two-factor-auhtentication, and full audit trail.</p>
                            </div>
                        </div>
                    </div>
                </section>

                {/* How it works  */}
                <section className="py-24 bg-gray-50">
                    <div className="max-w-7xl mx-auto px-6">
                        <h2 className="text-4xl font-bold text-center mb-16">Get started in under 5 minutes</h2>
                        <div className="grid md:grid-cols-3 gap-10">
                            <div className="text-center">
                                <div className="mx-auto w-20 h-20 bg-blue-600 text-white rounded-3xl flex items-center justify-center text-5xl font-bold mb-6 shadow-inner">1</div>
                                <h2 className="text-2xl font-semibold mb-3">Create Workspace</h2>
                                <p className="text-gray-600">Sign up and set your company in seconds.</p>
                            </div>

                            <div className="text-center">
                                <div className="mx-auto w-20 h-20 bg-blue-600 text-white rounded-3xl flex items-center justify-center text-5xl font-bold mb-6 shadow-inner">2</div>
                                <h2 className="text-2xl font-semibold mb-3">Add your Team</h2>
                                <p className="text-gray-600">Invite employees via email or Whatsapp.</p>
                            </div>

                            <div className="text-center">
                                <div className="mx-auto w-20 h-20 bg-blue-600 text-white rounded-3xl flex items-center justify-center text-5xl font-bold mb-6 shadow-inner">3</div>
                                <h2 className="text-2xl font-semibold mb-3">Pay in One Click</h2>
                                <p className="text-gray-600">Review and send salaries securely.</p>
                            </div>
                        </div>
                    </div>
                </section>

                {/*  Final CTA  */}
                <section className="py-28 bg-gradient-to-br from-blue-700 via-indigo-700 to-blue-800 text-white">
                    <div className="max-w-4xl mx-auto px-6 text-center">
                        <h2 className="text-5xl font-bold mb-6">Ready to make payroll effortless?</h2>
                        <p className="text-xl text-blue-100 mb-10">Join hundreds of Nigerians businesses already using Strexpei</p>

                        <Link to="" className="cta-btn inline-block bg-white text-blue-700 font-bold text-xl px-14 py-7 rounded-3xl hover:shadow-2xl">
                        Start Your Free Trial</Link>

                        <p className="mt-6 text-blue-200 text-base">No credit card required + Cancel anytime</p>
                    </div>
                </section>

                {/* Footer */}
                <footer className="bg-gray-950 text-gray-400 py-16">
                    <div className="max-w-7xl mx-auto px-6">
                        <div className="flex flex-col md:flex-row justify-between items-center gap-8">
                            <div>
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="text-2xl font-bold text-gray-50">Strex<span className="text-blue-600">Pei</span></div>
                                </div>
                                <p className="text-base">Modern payroll &amp; team management for Nigeria</p>
                            </div>

                            <p className="text-base">&copy; 2026 Strexpei. All rights reserved.</p>
                        </div>
                    </div>
                </footer>
            </main>
        </div>
    );
} 