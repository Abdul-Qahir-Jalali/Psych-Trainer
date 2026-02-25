import { useState, useEffect } from 'react';
import { supabase } from './lib/supabase';
import { AuthScreen } from './components/AuthScreen';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { EvaluationPanel } from './components/EvaluationPanel';

const API_BASE = 'http://localhost:8000/api'; // Change to empty string in production if serving from same origin

function App() {
    const [sessionToken, setSessionToken] = useState(null);
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [mobileTab, setMobileTab] = useState('chat');

    // App State
    const [sessions, setSessions] = useState([]);
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [phase, setPhase] = useState('OFFLINE');
    const [turnCount, setTurnCount] = useState(0);
    const [messages, setMessages] = useState([]);
    const [evalNotes, setEvalNotes] = useState([]);
    const [gradeReport, setGradeReport] = useState(null);
    
    // UI State
    const [isWaiting, setIsWaiting] = useState(false);
    const [currentStreamText, setCurrentStreamText] = useState('');

    // --- Authentication ---
    useEffect(() => {
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSessionToken(session?.access_token || null);
        });

        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
            setSessionToken(session?.access_token || null);
        });

        return () => subscription.unsubscribe();
    }, []);

    // --- Initial Load ---
    useEffect(() => {
        if (sessionToken) {
            loadSessionsList();
            handleNewSession(); // Default to new blank session
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionToken]);

    const getHeaders = () => {
        const headers = { 'Content-Type': 'application/json' };
        if (sessionToken) headers['Authorization'] = `Bearer ${sessionToken}`;
        return headers;
    };

    const loadSessionsList = async () => {
        try {
            const res = await fetch(`${API_BASE}/sessions`, { headers: getHeaders() });
            if (!res.ok) throw new Error('Failed to fetch sessions');
            const data = await res.json();
            setSessions(data.sessions || []);
        } catch (err) {
            console.error(err);
        }
    };

    const loadSession = async (id) => {
        if (!id) return;
        try {
            const res = await fetch(`${API_BASE}/session/${id}`, { headers: getHeaders() });
            if (!res.ok) throw new Error('Failed to load session');
            const data = await res.json();
            
            setCurrentSessionId(data.session_id);
            setPhase(data.is_ended && data.grade_report ? 'DEBRIEF' : data.phase || 'OFFLINE');
            setTurnCount(data.turn_count);
            setMessages(data.messages || []);
            setGradeReport(data.grade_report || null);
            setEvalNotes([]); // Past notes aren't currently preserved in backend history view, but we'll reset
            if (window.innerWidth < 768) setIsSidebarOpen(false);
        } catch (err) {
            console.error(err);
        }
    };

    const handleNewSession = () => {
        setCurrentSessionId(null);
        setPhase('OFFLINE');
        setTurnCount(0);
        setMessages([]);
        setEvalNotes([]);
        setGradeReport(null);
        setCurrentStreamText('');
        if (window.innerWidth < 768) setIsSidebarOpen(false);
    };

    const handleStartSession = async () => {
        try {
            setIsWaiting(true);
            const res = await fetch(`${API_BASE}/session/start`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({})
            });
            if (!res.ok) throw new Error('Failed to start session');
            const data = await res.json();
            
            setCurrentSessionId(data.session_id);
            setPhase(data.phase);
            setMessages([{ role: 'system', content: data.message }]);
            setEvalNotes(["Session started. Observing student's approach..."]);
            loadSessionsList();
        } catch (err) {
            console.error(err);
            setMessages(prev => [...prev, { role: 'system', content: `⚠️ Failed to start: ${err.message}` }]);
        } finally {
            setIsWaiting(false);
        }
    };

    const handleSendMessage = async (text) => {
        // If no session, start one first on the fly
        let activeSessionId = currentSessionId;
        if (!activeSessionId) {
            await handleStartSession();
            // In a real app we'd await state updates, but let's assume session id is fetched
            return; // Simplified flow: the user has to click start, or we intercept
        }

        setMessages(prev => [...prev, { role: 'student', content: text }]);
        setIsWaiting(true);
        setCurrentStreamText('');

        try {
            const res = await fetch(`${API_BASE}/session/stream_chat`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({ session_id: activeSessionId, message: text })
            });

            if (!res.ok) {
                if (res.status === 429) {
                    throw new Error("You are speaking too fast. Please wait a moment.");
                }
                throw new Error('API Request failed');
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let done = false;
            let buffer = "";
            let streamedResponse = "";
            let currentEvent = null;

            while (!done) {
                const { value, done: readerDone } = await reader.read();
                if (value) {
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line

                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (!line) continue;

                        if (line.startsWith('event: ')) {
                            currentEvent = line.substring(7).trim();
                        } else if (line.startsWith('data: ')) {
                            const dataStr = line.substring(6).trim();
                            try {
                                const data = JSON.parse(dataStr);
                                if (currentEvent === 'done') {
                                    setPhase(data.phase);
                                    setTurnCount(data.turn_count);
                                    if (data.professor_note) {
                                        setEvalNotes(prev => [...prev, data.professor_note]);
                                    }
                                    done = true;
                                    break;
                                } else if (currentEvent === 'error') {
                                    throw new Error(data.error);
                                } else if (data.token) {
                                    streamedResponse += data.token;
                                    setCurrentStreamText(streamedResponse);
                                }
                            } catch (e) {
                                console.warn("Parse error", e);
                            }
                            currentEvent = null;
                        }
                    }
                }
                if (readerDone) done = true;
            }

            // Commit final stream to messages
            setMessages(prev => [...prev, { role: 'patient', content: streamedResponse }]);
            setCurrentStreamText('');

        } catch (err) {
            console.error(err);
            setMessages(prev => [...prev, { role: 'system', content: `⚠️ Error: ${err.message}` }]);
            setCurrentStreamText('');
        } finally {
            setIsWaiting(false);
        }
    };

    const handleEndSession = async () => {
        if (!currentSessionId) return;
        if (!window.confirm('End the session and receive your grade?')) return;

        try {
            setIsWaiting(true);
            const res = await fetch(`${API_BASE}/session/end`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({ session_id: currentSessionId })
            });
            if (!res.ok) throw new Error('Failed to end session');
            const data = await res.json();
            
            setGradeReport(data.report);
            setPhase('DEBRIEF');
            setMessages(prev => [...prev, { role: 'system', content: '📋 Session ended. Your grade report is ready in the panel →' }]);
            loadSessionsList();
        } catch (err) {
            console.error(err);
            setMessages(prev => [...prev, { role: 'system', content: `⚠️ Grading error: ${err.message}` }]);
        } finally {
            setIsWaiting(false);
        }
    };

    const handleLogout = async () => {
        await supabase.auth.signOut();
        setSessionToken(null);
    };

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
                    <Sidebar 
                        sessions={sessions} 
                        currentSessionId={currentSessionId}
                        onNewSession={handleNewSession}
                        onSelectSession={loadSession}
                    />
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
                        <ChatPanel 
                            messages={messages} 
                            isWaiting={isWaiting} 
                            currentStreamText={currentStreamText}
                            onSendMessage={handleSendMessage}
                        />
                        <EvaluationPanel 
                            phase={phase}
                            turnCount={turnCount}
                            notes={evalNotes}
                            gradeReport={gradeReport}
                            onEndSession={handleEndSession}
                        />
                    </>
                )}
            </main>
        </div>
    );
}

export default App;
