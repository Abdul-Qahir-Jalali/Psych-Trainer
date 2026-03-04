import { useEffect } from 'react';
import { supabase } from './lib/supabase';
import { AuthScreen } from './components/AuthScreen';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { EvaluationPanel } from './components/EvaluationPanel';
import { useStore } from './store/useStore';

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

    // --- Authentication ---
    useEffect(() => {
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSessionToken(session?.access_token || null);
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

    if (!sessionToken) {
        return <AuthScreen />;
    }

    return (
        <div className={`app-container ${mobileTab === 'eval' ? 'show-eval-mobile' : ''}`}>
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
                    <div className="turn-counter">Turn {turnCount}</div>
                    <button className="btn-header-icon" onClick={handleLogout} title="Log out" style={{marginLeft: '12px'}}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                            <polyline points="16 17 21 12 16 7"></polyline>
                            <line x1="21" y1="12" x2="9" y2="12"></line>
                        </svg>
                    </button>
                </div>
            </header>

            <main id="app-main">
                <div className={`sidebar-wrapper ${isSidebarOpen ? 'open' : 'closed'}`}>
                    <Sidebar />
                </div>

                <div className="mobile-tabs" style={{ display: window.innerWidth < 768 ? 'flex' : 'none' }}>
                    <button className={`mobile-tab ${mobileTab === 'chat' ? 'active' : ''}`} onClick={() => setMobileTab('chat')}>💬 Chat</button>
                    <button className={`mobile-tab ${mobileTab === 'eval' ? 'active' : ''}`} onClick={() => setMobileTab('eval')}>📊 Evaluation</button>
                </div>

                {!currentSessionId ? (
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-card)'}}>
                        <div style={{ textAlign: 'center'}}>
                            <h2 style={{ marginBottom: '1rem'}}>Ready for a new patient?</h2>
                            <button className="btn-primary" onClick={handleStartSession} disabled={isWaiting}>
                                {isWaiting ? 'Starting...' : '▶ Begin Session'}
                            </button>
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
