import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Explore from './pages/Explore';
import Generate from './pages/Generate';
import Login from './pages/Login';
import './App.css';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="app">
          <Navbar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/explore" element={<Explore />} />
              <Route path="/generate" element={<Generate />} />
              <Route path="/login" element={<Login />} />
            </Routes>
          </main>
          <footer className="footer">
            <p>Raaga.AI — Carnatic Classical Music Generation Platform</p>
          </footer>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
