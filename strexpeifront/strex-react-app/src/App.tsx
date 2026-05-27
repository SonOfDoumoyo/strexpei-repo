import Login from "./pages/Login";
import Header from "./components/Header";
import Home from "./pages/Home";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import SignUp from "./pages/Signup";
import JoinCreate from "./pages/joinCreate";
import CreateCompany from "./pages/CreateComp";
import JoinCompany from "./pages/JoinComp";
import VerifyAccount from "./pages/VerifyAcc";
import Profile from "./pages/profile";
import HomeLayout from "./pages/HomeLayout";
import Notification from "./pages/Notify";
import logo from "../src/assets/images/strexpei-logo.png";
import "./App.css";
import { UserProvider } from './context/userContext.tsx';
import AppPage from "./pages/apppage.tsx";
// import ProtectedRoute from "./context/ProtectRoute.tsx";

function App () {


  return (
    <Router>
      <UserProvider>
      <Routes>
        <Route path="/" element={<AppPage />}/>
        <Route path="/sign-in" element={<Login />}/>
        <Route path="/sign-up" element={<SignUp />}/>
        <Route path="/verify-account" element={<VerifyAccount />}/>
        <Route path="/header" element={<Header />}/>
        <Route element={<HomeLayout/>}>
          <Route path="/home/:uid" element={<Home />}/>
          <Route path="/workspace" element={<JoinCreate />}/>
          <Route path="/workspace/create-company/:uid" element={<CreateCompany />}/>
          <Route path="/workspace/join-company/:uid" element={<JoinCompany />}/>
          <Route path="/organisations/:uid" element={<JoinCompany/>}/>
          <Route path="/profile/:uid" element={<Profile />}/>
          <Route path="/notifications/:uid" element={<Notification/>}/>
        </Route>
      </Routes>
      </UserProvider>
    </Router>
  );
}

export default App;