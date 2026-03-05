import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Music, LogOut } from 'lucide-react';

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        <div className="brand-icon">
          <Music size={20} color="#fff" />
        </div>
        <span className="gradient-text">Raaga.AI</span>
      </Link>

      <div className="nav-links">
        <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`}>
          Home
        </Link>
        <Link to="/explore" className={`nav-link ${isActive('/explore') ? 'active' : ''}`}>
          Explore
        </Link>
        <Link to="/generate" className={`nav-link ${isActive('/generate') ? 'active' : ''}`}>
          Create
        </Link>
      </div>

      <div className="nav-user">
        {user ? (
          <>
            <div className="user-details">
              <span className="user-email">{user.email}</span>
              <span className="tier-badge">{user.tier}</span>
            </div>
            <button onClick={logout} className="logout-btn" title="Logout">
              <LogOut size={14} />
              <span>Logout</span>
            </button>
          </>
        ) : (
          <Link to="/login" className="btn btn-primary">
            Sign In
          </Link>
        )}
      </div>
    </nav>
  );
}
