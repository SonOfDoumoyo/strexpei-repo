import Login from "./pages/Login";
import Header from "./components/Header";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
function App () {

  return (
    <Router>
      <Routes>
        <Route element={<Layout/>}>
          <Route path="/" element={<Login />}/>
        </Route>
        <Route path="/Header" element={<Header />}/>
      </Routes>
    </Router>
  );
}

export default App;