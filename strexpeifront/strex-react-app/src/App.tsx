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

function App () {

  return (
    <Router>
      <Routes>
        <Route path="/sign-in" element={<Login />}/>
        <Route path="/sign-up" element={<SignUp />}/>
        <Route path="/verify-account" element={<VerifyAccount />}/>
        <Route path="/header" element={<Header />}/>
        <Route path="/workspace" element={<JoinCreate />}/>
        <Route path="/create-company" element={<CreateCompany />}/>
        <Route path="/join-company" element={<JoinCompany />}/>
        <Route path="/home" element={<Home />}/>
      </Routes>
    </Router>
  );
}

export default App;