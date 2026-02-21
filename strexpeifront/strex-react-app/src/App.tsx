import './App.css'
//import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import SignUp from './pages/Signup'
import Home from './pages/Home'
import Header from './components/header'

function App() {

  const HomePage = () => (
      <>
        <Header />
        <Home />
      </>
  );

  return (
    <Router>
      <Routes>
        <Route path='/' element={<SignUp />} />
        <Route path='/home' element={<HomePage />}/>
      </Routes>
    </Router>
  )
}

export default App
