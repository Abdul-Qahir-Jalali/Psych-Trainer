import { useState } from 'react';
import { supabase } from '../lib/supabase';

export function AuthScreen() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const [isLoginView, setIsLoginView] = useState(false);

    const handleAuth = async (e: React.FormEvent) => {
        e.preventDefault();
        setErrorMsg('');
        setSuccessMsg('');
        if (!email || !password) return;
        
        setLoading(true);
        if (isLoginView) {
            const { error } = await supabase.auth.signInWithPassword({ email, password });
            if (error) setErrorMsg(error.message);
        } else {
            const { data, error } = await supabase.auth.signUp({ 
                email, 
                password,
                options: { data: { full_name: name } }
            });

            if (error) {
                setErrorMsg(error.message);
            } else if (data?.user?.identities && data.user.identities.length === 0) {
                setIsLoginView(true); 
                setErrorMsg('This email is already registered. Please enter your password to log in.');
                setPassword(''); 
            } else {
                setSuccessMsg('Registration successful! Please check your email inbox for a confirmation link to activate your account.');
                setEmail('');
                setPassword('');
            }
        }

        setLoading(false);
    };

    const handleGoogle = async () => {
        await supabase.auth.signInWithOAuth({ provider: 'google' });
    };

    return (
        <div style={styles.container}>
            <div style={styles.card}>
                <h2 style={styles.mainTitle}>Welcome to PsychTrainer</h2>
                <h3 style={styles.subTitle}>{isLoginView ? 'Log in' : 'Sign up'}</h3>
                
                <form onSubmit={handleAuth} style={styles.form}>
                    {!isLoginView && (
                        <div style={styles.inputWrapper}>
                            <label style={styles.floatingLabel}>Name</label>
                            <input 
                                type="text" 
                                style={styles.inputActive}
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                            />
                        </div>
                    )}
                    
                    <div style={styles.inputWrapper}>
                        <input 
                            type="email" 
                            placeholder="Email"
                            style={styles.input}
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required 
                        />
                    </div>
                    
                    <div style={styles.inputWrapper}>
                        <input 
                            type={showPassword ? "text" : "password"} 
                            placeholder="Password"
                            style={styles.input}
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required 
                        />
                        <span style={styles.eyeIcon} onClick={() => setShowPassword(!showPassword)}>
                            {showPassword ? (
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                    <circle cx="12" cy="12" r="3"></circle>
                                </svg>
                            ) : (
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2">
                                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                    <line x1="1" y1="1" x2="23" y2="23"></line>
                                </svg>
                            )}
                        </span>
                    </div>
                    
                    {errorMsg && <div style={styles.error}>{errorMsg}</div>}
                    {successMsg && <div style={styles.success}>{successMsg}</div>}

                    <button type="submit" disabled={loading} style={styles.primaryButton}>
                        {loading ? 'Processing...' : (isLoginView ? 'Log In' : 'Sign Up')}
                    </button>
                    
                    <div style={styles.toggleText}>
                        {isLoginView ? "Don't have an account? " : "Already have an account? "}
                        <span style={styles.link} onClick={() => { setIsLoginView(!isLoginView); setErrorMsg(''); }}>
                            {isLoginView ? 'Sign Up' : 'Log In'}
                        </span>
                    </div>

                    <div style={styles.divider}>
                        <span style={styles.dividerLine}></span>
                        <span style={styles.dividerText}>or</span>
                        <span style={styles.dividerLine}></span>
                    </div>

                    <button type="button" onClick={handleGoogle} style={styles.googleButton}>
                        <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="G" style={styles.googleIcon} />
                        {isLoginView ? 'Log in with Google' : 'Sign up with Google'}
                    </button>
                </form>
            </div>
        </div>
    );
}

const styles = {
    container: { display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: '#f9fafb', fontFamily: "'Inter', sans-serif" },
    card: { backgroundColor: '#fff', padding: '40px', borderRadius: '16px', boxShadow: '0 10px 25px rgba(0,0,0,0.05)', width: '100%', maxWidth: '400px', boxSizing: 'border-box' as const },
    mainTitle: { textAlign: 'center' as const, fontSize: '24px', color: '#111', marginBottom: '5px', fontWeight: 'bold', marginTop: 0 },
    subTitle: { textAlign: 'center' as const, fontSize: '18px', color: '#555', marginBottom: '25px', fontWeight: 'normal', marginTop: 0 },
    form: { display: 'flex', flexDirection: 'column' as const, gap: '20px' },
    inputWrapper: { position: 'relative' as const, display: 'flex', flexDirection: 'column' as const },
    floatingLabel: { position: 'absolute' as const, top: '-8px', left: '12px', backgroundColor: '#fff', padding: '0 4px', fontSize: '12px', color: '#0095ff', fontWeight: 500, zIndex: 1 },
    input: { padding: '14px', borderRadius: '6px', border: '1px solid #ddd', fontSize: '15px', outline: 'none', width: '100%', boxSizing: 'border-box' as const },
    inputActive: { padding: '14px', borderRadius: '6px', border: '2px solid #0095ff', fontSize: '15px', outline: 'none', width: '100%', boxSizing: 'border-box' as const },
    eyeIcon: { position: 'absolute' as const, right: '14px', top: '14px', cursor: 'pointer' },
    primaryButton: { backgroundColor: '#0095ff', color: 'white', border: 'none', padding: '14px', borderRadius: '6px', fontSize: '16px', fontWeight: 'bold', cursor: 'pointer', marginTop: '10px' },
    toggleText: { textAlign: 'center' as const, fontSize: '14px', color: '#888' },
    link: { color: '#0095ff', cursor: 'pointer', fontWeight: 'bold' },
    divider: { display: 'flex', alignItems: 'center', margin: '10px 0' },
    dividerLine: { flex: 1, height: '1px', backgroundColor: '#ddd' },
    dividerText: { padding: '0 10px', color: '#aaa', fontSize: '14px' },
    googleButton: { display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff', border: '1px solid #ddd', padding: '12px', borderRadius: '6px', fontSize: '15px', fontWeight: 500, cursor: 'pointer', color: '#333' },
    googleIcon: { width: '20px', height: '20px', marginRight: '10px' },
    error: { color: '#ff6b6b', fontSize: '14px', textAlign: 'center' as const },
    success: { color: '#10b981', fontSize: '14px', textAlign: 'center' as const }
}
