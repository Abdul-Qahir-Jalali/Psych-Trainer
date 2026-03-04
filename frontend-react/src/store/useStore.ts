import { create } from 'zustand';
import { supabase } from '../lib/supabase';
import { fetchEventSource } from '@microsoft/fetch-event-source';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface StoreState {
    // Auth
    sessionToken: string | null;
    setSessionToken: (token: string | null) => void;
    
    // UI State
    isSidebarOpen: boolean;
    setIsSidebarOpen: (isOpen: boolean) => void;
    mobileTab: string;
    setMobileTab: (tab: string) => void;
    isWaiting: boolean;
    setIsWaiting: (waiting: boolean) => void;
    currentStreamText: string;
    setCurrentStreamText: (text: string) => void;
    failedMessage: string;
    setFailedMessage: (msg: string) => void;

    // Session State
    sessions: any[];
    currentSessionId: string | null;
    phase: string;
    turnCount: number;
    messages: any[];
    evalNotes: any[];
    gradeReport: any | null;

    // Actions
    setSessions: (sessions: any[]) => void;
    setCurrentSessionId: (id: string | null) => void;
    setPhase: (phase: string) => void;
    setTurnCount: (count: number) => void;
    setMessages: (updater: any) => void;
    setEvalNotes: (updater: any) => void;
    setGradeReport: (report: any | null) => void;

    // Thunks
    loadSessionsList: () => Promise<void>;
    loadSession: (id: string) => Promise<void>;
    handleNewSession: () => void;
    handleStartSession: () => Promise<void>;
    handleSendMessage: (text: string) => Promise<void>;
    handleEndSession: () => Promise<void>;
    handleLogout: () => Promise<void>;
}

export const useStore = create<StoreState>((set, get) => ({
    // Auth
    sessionToken: null,
    setSessionToken: (token) => set({ sessionToken: token }),

    // UI State
    isSidebarOpen: false,
    setIsSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
    mobileTab: 'chat',
    setMobileTab: (tab) => set({ mobileTab: tab }),
    isWaiting: false,
    setIsWaiting: (waiting) => set({ isWaiting: waiting }),
    currentStreamText: '',
    setCurrentStreamText: (text) => set({ currentStreamText: text }),
    failedMessage: '',
    setFailedMessage: (msg) => set({ failedMessage: msg }),

    // Session State
    sessions: [],
    currentSessionId: null,
    phase: 'OFFLINE',
    turnCount: 0,
    messages: [],
    evalNotes: [],
    gradeReport: null,

    // Actions
    setSessions: (sessions) => set({ sessions }),
    setCurrentSessionId: (id) => set({ currentSessionId: id }),
    setPhase: (phase) => set({ phase }),
    setTurnCount: (count) => set({ turnCount: count }),
    setMessages: (updater) => set((state) => ({ 
        messages: typeof updater === 'function' ? updater(state.messages) : updater 
    })),
    setEvalNotes: (updater) => set((state) => ({ 
        evalNotes: typeof updater === 'function' ? updater(state.evalNotes) : updater 
    })),
    setGradeReport: (report) => set({ gradeReport: report }),

    // Thunks
    loadSessionsList: async () => {
        const { sessionToken } = get();
        try {
            const res = await fetch(`${API_BASE}/sessions`, { 
                headers: { 
                    'Content-Type': 'application/json',
                    ...(sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {})
                } 
            });
            if (!res.ok) throw new Error('Failed to fetch sessions');
            const data = await res.json();
            set({ sessions: data.sessions || [] });
        } catch (err) {
            console.error(err);
        }
    },

    loadSession: async (id: string) => {
        if (!id) return;
        const { sessionToken } = get();
        try {
            const res = await fetch(`${API_BASE}/session/${id}`, { 
                headers: { 
                    'Content-Type': 'application/json',
                    ...(sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {})
                } 
            });
            if (!res.ok) throw new Error('Failed to load session');
            const data = await res.json();
            
            set({
                currentSessionId: data.session_id,
                phase: (data.is_ended && data.grade_report) ? 'DEBRIEF' : (data.phase || 'OFFLINE'),
                turnCount: data.turn_count,
                messages: data.messages || [],
                gradeReport: data.grade_report || null,
                evalNotes: [],
            });
            if (window.innerWidth < 768) set({ isSidebarOpen: false });
        } catch (err) {
            console.error(err);
        }
    },

    handleNewSession: () => {
        set({
            currentSessionId: null,
            phase: 'OFFLINE',
            turnCount: 0,
            messages: [],
            evalNotes: [],
            gradeReport: null,
            currentStreamText: ''
        });
        if (window.innerWidth < 768) set({ isSidebarOpen: false });
    },

    handleStartSession: async () => {
        const { sessionToken, loadSessionsList } = get();
        try {
            set({ isWaiting: true });
            const res = await fetch(`${API_BASE}/session/start`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...(sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {})
                },
                body: JSON.stringify({})
            });
            if (!res.ok) throw new Error('Failed to start session');
            const data = await res.json();
            
            set({
                currentSessionId: data.session_id,
                phase: data.phase,
                messages: [{ role: 'system', content: data.message }],
                evalNotes: ["Session started. Observing student's approach..."]
            });
            await loadSessionsList();
        } catch (err: any) {
            console.error(err);
            set((state) => ({ messages: [...state.messages, { role: 'system', content: `⚠️ Failed to start: ${err.message}` }] }));
        } finally {
            set({ isWaiting: false });
        }
    },

    handleSendMessage: async (text: string) => {
        const { currentSessionId, sessionToken, handleStartSession, setPhase, setTurnCount, setEvalNotes } = get();
        
        let activeSessionId = currentSessionId;
        if (!activeSessionId) {
            await handleStartSession();
            return;
        }

        set((state) => ({ 
            messages: [...state.messages, { role: 'student', content: text }],
            isWaiting: true,
            currentStreamText: ''
        }));

        try {
            let streamedResponse = "";
            let finalMessages: any[] = [];

            await fetchEventSource(`${API_BASE}/session/stream_chat`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...(sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {})
                },
                body: JSON.stringify({ session_id: activeSessionId, message: text }),
                onmessage(ev) {
                    if (ev.event === 'done') {
                        try {
                            const data = JSON.parse(ev.data);
                            setPhase(data.phase);
                            setTurnCount(data.turn_count);
                            if (data.professor_note) {
                                setEvalNotes((prev: any[]) => [...prev, data.professor_note]);
                            }
                        } catch (e) {
                            console.warn("Parse error on 'done' event", e);
                        }
                    } else if (ev.event === 'error') {
                        throw new Error(JSON.parse(ev.data).error || "Stream Error");
                    } else if (ev.event === 'message' || ev.event === '') {
                        try {
                            const data = JSON.parse(ev.data);
                            if (data.token) {
                                streamedResponse += data.token;
                                set({ currentStreamText: streamedResponse });
                            }
                        } catch (e) {
                            console.warn("Parse error on message data", e);
                        }
                    }
                },
                onerror(err) {
                    throw err; 
                },
                onclose() {
                    set((state) => {
                        finalMessages = [...state.messages, { role: 'patient', content: streamedResponse }];
                        return { messages: finalMessages, currentStreamText: '' };
                    });
                }
            });

        } catch (err: any) {
            console.error(err);
            set((state) => {
                const newMsgs = [...state.messages];
                if (newMsgs.length > 0 && newMsgs[newMsgs.length - 1].role === 'student') {
                    newMsgs.pop();
                }
                newMsgs.push({ role: 'system', content: `⚠️ Connection Failed: ${err.message}. Your text has been restored below so you can try again.` });
                return { 
                    messages: newMsgs,
                    failedMessage: text,
                    currentStreamText: ''
                };
            });
        } finally {
            set({ isWaiting: false });
        }
    },

    handleEndSession: async () => {
        const { currentSessionId, sessionToken, loadSessionsList } = get();
        if (!currentSessionId) return;
        if (!window.confirm('End the session and receive your grade?')) return;

        try {
            set({ isWaiting: true });
            const res = await fetch(`${API_BASE}/session/end`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...(sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {})
                },
                body: JSON.stringify({ session_id: currentSessionId })
            });
            if (!res.ok) throw new Error('Failed to end session');
            const data = await res.json();
            
            set((state) => ({
                gradeReport: data.report,
                phase: 'DEBRIEF',
                messages: [...state.messages, { role: 'system', content: '📋 Session ended. Your grade report is ready in the panel →' }]
            }));
            await loadSessionsList();
        } catch (err: any) {
            console.error(err);
            set((state) => ({ messages: [...state.messages, { role: 'system', content: `⚠️ Grading error: ${err.message}` }] }));
        } finally {
            set({ isWaiting: false });
        }
    },

    handleLogout: async () => {
        await supabase.auth.signOut();
        set({ sessionToken: null });
    }
}));
