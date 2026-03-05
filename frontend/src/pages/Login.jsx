import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { LogIn, UserPlus, Loader } from 'lucide-react';

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
      navigate('/generate');
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card animate-fade-in">
        <h1>{isRegister ? 'Create Account' : 'Welcome Back'}</h1>
        <p className="auth-subtitle">
          {isRegister
            ? 'Join Raaga.AI to save and manage your compositions'
            : 'Sign in to continue your musical journey'}
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isRegister ? 'Min 8 characters' : 'Your password'}
              required
              minLength={isRegister ? 8 : undefined}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="btn btn-primary btn-lg btn-full" disabled={loading}>
            {loading ? (
              <><Loader size={16} className="spin" /> Please wait...</>
            ) : isRegister ? (
              <><UserPlus size={16} /> Create Account</>
            ) : (
              <><LogIn size={16} /> Sign In</>
            )}
          </button>
        </form>

        <div className="auth-switch">
          {isRegister ? (
            <p>Already have an account? <button onClick={() => setIsRegister(false)} className="link-btn">Sign in</button></p>
          ) : (
            <p>Don't have an account? <button onClick={() => setIsRegister(true)} className="link-btn">Create one</button></p>
          )}
        </div>

        <div className="demo-hint">
          <p>Demo: <code>demo@raaga.ai</code> / <code>demo1234</code></p>
        </div>
      </div>
    </div>
  );
}
