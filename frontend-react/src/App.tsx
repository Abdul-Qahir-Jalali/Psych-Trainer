import { useEffect, useState } from 'react';
import { supabase } from './lib/supabase';
import { AuthScreen } from './components/AuthScreen';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { EvaluationPanel } from './components/EvaluationPanel';
import { useStore } from './store/useStore';
const PATIENTS = [
    {
        id: 1,
        name: "James",
        age: 21,
        headline: "Obsessive-Compulsive Disorder (OCD)",
        description: "James is a college student struggling with severe contamination fears. He washes his hands 30+ times a day and avoids public transport. He presents as highly anxious, intelligent, but severely distressed by intrusive thoughts and constantly seeks reassurance."
    }
];

function App() {
    const sessionToken = useStore(state => state.sessionToken);
    const setSessionToken = useStore(state => state.setSessionToken);
    const loadSessionsList = useStore(state => state.loadSessionsList);
    const handleNewSession = useStore(state => state.handleNewSession);
    
    const isSidebarOpen = useStore(state => state.isSidebarOpen);
    const setIsSidebarOpen = useStore(state => state.setIsSidebarOpen);
    const mobileTab = useStore(state => state.mobileTab);
    const setMobileTab = useStore(state => state.setMobileTab);
    const phase = useStore(state => state.phase);
    const turnCount = useStore(state => state.turnCount);
    const isWaiting = useStore(state => state.isWaiting);
    const currentSessionId = useStore(state => state.currentSessionId);
    const handleLogout = useStore(state => state.handleLogout);
    const handleStartSession = useStore(state => state.handleStartSession);
    const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);
    const failedMessage = useStore(state => state.failedMessage);
    // --- Authentication ---
    useEffect(() => {
        supabase.auth.getUser().then(({ data: { user }, error }) => {
            if (error || !user) {
                supabase.auth.signOut();
                setSessionToken(null);
            } else {
                supabase.auth.getSession().then(({ data: { session } }) => {
                    setSessionToken(session?.access_token || null);
                });
            }
        });

        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            setSessionToken(session?.access_token || null);
        });

        return () => subscription.unsubscribe();
    }, [setSessionToken]);


    // --- Initial Load ---
    useEffect(() => {
        if (sessionToken) {
            loadSessionsList();
            handleNewSession(); // Default to new blank session
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionToken]);
    // --- Keyboard Shortcuts ---
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Listen for Ctrl + Shift + S
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 's') {
                e.preventDefault(); // Prevent the browser from trying to save the page
                setIsSidebarOpen(!isSidebarOpen);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isSidebarOpen, setIsSidebarOpen]);

    if (!sessionToken) {
        return <AuthScreen />;
    }

    return (
        <div className={`app-container ${mobileTab === 'eval' ? 'show-eval-mobile' : ''}`} style={{ height: '100vh', width: '100vw', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <header id="app-header">
                <div className="header-left">
                    <button 
                        className="btn-header-icon" 
                        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                        title="Toggle Sidebar"
                    >
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="4" y1="8" x2="20" y2="8"></line>
                            <line x1="4" y1="16" x2="14" y2="16"></line>
                        </svg>
                    </button>
                    <div>
                        <h1>PsychTrainer</h1>
                        <p className="subtitle">Clinical Simulation Platform</p>
                    </div>
                </div>
                <div className="header-right">
                    <div className="phase-badge active" id="phase-badge">
                        <span className="phase-dot"></span>
                        <span id="phase-label">{phase.toUpperCase()}</span>
                    </div>
                </div>
            </header>

            <main id="app-main" style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                <div className={`sidebar-wrapper ${isSidebarOpen ? 'open' : 'closed'}`}>
                    <Sidebar />
                </div>

                <div className="mobile-tabs">
                    <button className={`mobile-tab ${mobileTab === 'chat' ? 'active' : ''}`} onClick={() => setMobileTab('chat')}>💬 Chat</button>
                    <button className={`mobile-tab ${mobileTab === 'eval' ? 'active' : ''}`} onClick={() => setMobileTab('eval')}>📊 Evaluation</button>
                </div>

                            {!currentSessionId ? (
                    <div style={{ flex: 1, padding: '40px 20px', overflowY: 'auto', background: 'var(--bg-main)' }}>
                        <div style={{ maxWidth: '750px', margin: '0 auto' }}>
                            <h2 style={{ marginBottom: '8px', fontSize: '28px', color: 'var(--text-primary)' }}>Select a Patient</h2>
                            <p style={{ color: 'var(--text-secondary)', marginBottom: '32px', fontSize: '16px' }}>Choose a patient profile below to review their details and begin your clinical simulation.</p>
                            {failedMessage && (
                                <div style={{ backgroundColor: '#ffebee', color: '#c62828', padding: '12px 16px', borderRadius: '8px', marginBottom: '24px', fontWeight: 500, border: '1px solid #ffcdd2' }}>
                                    ⚠️ {failedMessage}
                                </div>
                            )}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                {PATIENTS.map(patient => (
                                    <div key={patient.id} style={{ 
                                        backgroundColor: 'var(--bg-card)', 
                                        border: `2px solid ${selectedPatientId === patient.id ? 'var(--accent-primary)' : 'var(--border)'}`,
                                        borderRadius: 'var(--radius-lg)',
                                        padding: '24px',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s ease',
                                        boxShadow: selectedPatientId === patient.id ? '0 8px 24px rgba(0,149,255,0.12)' : '0 2px 8px rgba(0,0,0,0.03)'
                                    }} onClick={() => setSelectedPatientId(selectedPatientId === patient.id ? null : patient.id)}>
                                        
                                        {/* 1. Top Header Area */}
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                            <div>
                                                <h3 style={{ margin: '0 0 6px 0', fontSize: '20px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    {patient.name} <span style={{ fontSize: '14px', fontWeight: 'normal', color: 'var(--text-muted)' }}>• {patient.age} yrs</span>
                                                </h3>
                                                <div style={{ color: 'var(--accent-primary)', fontWeight: 600, fontSize: '15px' }}>{patient.headline}</div>
                                            </div>
                                            
                                            <span style={{ color: 'var(--text-muted)', fontSize: '14px', fontWeight: 500, whiteSpace: 'nowrap', marginLeft: '12px' }}>
                                                {selectedPatientId === patient.id ? 'Hide details ↑' : 'Click to view details ↓'}
                                            </span>
                                        </div>
                                        
                                        {/* 2. Expandable Description */}
                                        {selectedPatientId === patient.id && (
                                            <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border)', color: 'var(--text-secondary)', lineHeight: '1.6', fontSize: '15px' }}>
                                                <strong style={{ color: 'var(--text-primary)' }}>Clinical Background:</strong><br/>
                                                <span style={{ display: 'inline-block', marginTop: '6px' }}>{patient.description}</span>
                                            </div>
                                        )}
                                        
                                        {/* 3. Always-Visible Action Button at the Bottom */}
                                        <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
                                            <button 
                                                className="btn-primary" 
                                                onClick={(e) => { e.stopPropagation(); handleStartSession(); }} 
                                                disabled={isWaiting} 
                                                style={{ width: '100%', padding: '12px', fontSize: '16px', justifyContent: 'center' }}
                                            >
                                                {isWaiting ? 'Starting...' : '▶ Begin Session'}
                                            </button>
                                        </div>
                                        
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : (

                    <>
                        <ChatPanel />
                        <EvaluationPanel />
                    </>
                )}
            </main>
        </div>
    );
}

export default App;
