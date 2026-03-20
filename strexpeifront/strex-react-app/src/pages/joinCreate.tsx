import '../assets/css/main.css';
import '../assets/css/worksp.css';
import logo from '../assets/images/strexpei-logo.png';
import { useNavigate } from 'react-router-dom';
import api from '../api';

function JoinCreate () {
    const navigate = useNavigate();

    const handleCreateClick = () => {
        navigate('/create-company');
    }

    const handleJoinClick = () => {
        navigate('/join-company');
    }

    const handleLogout = async () => {
        try {
            await api.post('/auths/logout')
        } catch (err) {}
        finally {
            navigate('/sign-in', {replace: true})
        }
    }

    return (
        <>
          <div className="screen work-screen">
            <div className='card work-card'>
                <img src={logo} alt="Logo" className="log"/>
                <div className='logo-box'>
                    <h1>Welcome to Strexpei</h1>
                </div>

                <div className='join-create'>
                    <button className='manager-btn join-btn' onClick={handleCreateClick}>create organisation</button>
                    <button className='manager-btn create-btn' onClick={handleJoinClick}>join organisation</button>
                </div>
                <div className='line-box'>
                    <hr className='line left-line'></hr>
                    <p>or log out</p>
                    <hr className='line right-line'></hr>
                    <button className='manager-btn exit-btn' onClick={handleLogout}>Logout<i className='bx bx-log-out'/></button>
                </div>
            </div>
          </div>  
        </>
    );
}

export default JoinCreate;