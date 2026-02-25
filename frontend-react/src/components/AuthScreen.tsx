import { useState } from 'react';
import { supabase } from '../lib/supabase';

export function AuthScreen() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');
    const [successMsg, setSuccessMsg] = useState('');

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMsg('');
        if (!email || !password) return;
        
        setLoading(true);
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        setLoading(false);
        
        if (error) {
            setErrorMsg(error.message);
        }
    };

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMsg('');
        setSuccessMsg('');
        if (!email || !password) return;
        
        setLoading(true);
        const { data, error } = await supabase.auth.signUp({ email, password });
        setLoading(false);
        
        if (error) {
            setErrorMsg(error.message);
        } else {
            setSuccessMsg('Success! You are now registered and logged in.');
        }
    };

    return (
        <div className="login-screen">
            <div className="login-box">
                <div className="login-icon">🩺</div>
                <h2>Welcome to PsychTrainer</h2>
                <p>Please log in or sign up to securely access your clinical simulations.</p>
                
                <form>
                    <div className="input-group">
                        <input 
                            type="email" 
                            placeholder="Email address"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required 
                        />
                    </div>
                    <div className="input-group">
                        <input 
                            type="password" 
                            placeholder="Password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required 
                        />
                    </div>
                    
                    {errorMsg && (
                        <div className="auth-error" style={{ color: '#ff6b6b', marginTop: '10px', fontSize: '0.9rem' }}>
                            {errorMsg}
                        </div>
                    )}
                    {successMsg && (
                        <div className="auth-success" style={{ color: '#10b981', marginTop: '10px', fontSize: '0.9rem' }}>
                            {successMsg}
                        </div>
                    )}

                    <div className="auth-buttons">
                        <button 
                            type="submit" 
                            onClick={handleLogin} 
                            disabled={loading}
                            className="btn-primary"
                        >
                            {loading ? 'Loading...' : 'Log In'}
                        </button>
                        <button 
                            type="button" 
                            onClick={handleSignup} 
                            disabled={loading}
                            className="btn-secondary"
                        >
                            {loading ? 'Processing...' : 'Sign Up'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
