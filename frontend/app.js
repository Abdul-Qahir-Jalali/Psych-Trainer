/**
 * PsychTrainer — Frontend Application Logic
 *
 * Handles session management, REST API communication,
 * message rendering, and grade report visualization.
 */

// ═══════════════════════════════════════════════════════
//  State
// ═══════════════════════════════════════════════════════

let sessionId = null;
let isWaitingForResponse = false;

// ═══════════════════════════════════════════════════════
//  DOM References
// ═══════════════════════════════════════════════════════

const welcomeScreen   = document.getElementById('welcome-screen');
const chatMessages    = document.getElementById('chat-messages');
const inputBar        = document.getElementById('input-bar');
const messageInput    = document.getElementById('message-input');
const btnSend         = document.getElementById('btn-send');
const btnStart        = document.getElementById('btn-start');
const btnEnd          = document.getElementById('btn-end');

// ═══════════════════════════════════════════════════════
//  Mobile Responsiveness Toggles
// ═══════════════════════════════════════════════════════

function switchMobileTab(target) {
  const tabs = document.querySelectorAll('.mobile-tab');
  
  if (target === 'chat') {
    document.body.classList.remove('show-eval-mobile');
    tabs[0].classList.add('active'); // Chat tab
    tabs[1].classList.remove('active'); // Eval tab
  } else if (target === 'eval') {
    document.body.classList.add('show-eval-mobile');
    tabs[1].classList.add('active'); // Eval tab
    tabs[0].classList.remove('active'); // Chat tab
  }
}
const typingIndicator = document.getElementById('typing-indicator');
const phaseBadge      = document.getElementById('phase-badge');
const phaseLabel      = document.getElementById('phase-label');
const turnCounter     = document.getElementById('turn-counter');
const evalNotes       = document.getElementById('eval-notes');
const gradeReport     = document.getElementById('grade-report');
const sessionList     = document.getElementById('session-list');
const sidebar         = document.getElementById('sidebar');

// ═══════════════════════════════════════════════════════
//  Authentication (Supabase)
// ═══════════════════════════════════════════════════════

const SUPABASE_URL = 'https://xlkriwqjkbfepbuvsvch.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_xVLDBnTqgRAeTN1obV5veA_QxOJLdoV';
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

let sessionToken = null;

// Listen for auth changes
supabase.auth.onAuthStateChange((event, session) => {
    const loginScreen = document.getElementById('login-screen');
    const appHeader = document.getElementById('app-header');
    const appMain = document.getElementById('app-main');
    
    if (session) {
        sessionToken = session.access_token;
        loginScreen.style.display = 'none';
        appHeader.style.display = 'flex';
        appMain.style.display = 'flex';
        initApp(); // Loads lists and starts session if needed
    } else {
        sessionToken = null;
        loginScreen.style.display = 'flex';
        appHeader.style.display = 'none';
        appMain.style.display = 'none';
    }
});

async function handleLogin() {
    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-password').value;
    const errorDiv = document.getElementById('auth-error');
    const btn = document.getElementById('btn-login');
    
    if(!email || !password) return;
    btn.textContent = 'Loading...';
    
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    
    btn.textContent = 'Log In';
    if (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.color = '#ff6b6b';
        errorDiv.style.display = 'block';
    } else {
        errorDiv.style.display = 'none';
    }
}

async function handleSignUp() {
    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-password').value;
    const errorDiv = document.getElementById('auth-error');
    const btn = document.getElementById('btn-signup');
    
    if(!email || !password) return;
    btn.textContent = 'Loading...';
    
    const { error } = await supabase.auth.signUp({ email, password });
    
    btn.textContent = 'Sign Up';
    if (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.color = '#ff6b6b';
        errorDiv.style.display = 'block';
    } else {
        errorDiv.textContent = 'Success! You are now registered and logged in.';
        errorDiv.style.color = '#10b981';
        errorDiv.style.display = 'block';
    }
}

async function handleLogout() {
    await supabase.auth.signOut();
    sessionId = null;
    localStorage.removeItem('psychtrainer_session_id');
    document.getElementById('session-list').innerHTML = '';
}

// ═══════════════════════════════════════════════════════
//  API Helpers
// ═══════════════════════════════════════════════════════

const API_BASE = '';  // Same origin

async function apiPost(endpoint, body = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (sessionToken) headers['Authorization'] = `Bearer ${sessionToken}`;
    
    const res = await fetch(`${API_BASE}/api${endpoint}`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

// ═══════════════════════════════════════════════════════
//  Session Management
// ═══════════════════════════════════════════════════════

async function startSession() {
    btnStart.disabled = true;
    btnStart.innerHTML = '<span class="btn-icon">⏳</span> Starting...';

    try {
        const data = await apiPost('/session/start');
        sessionId = data.session_id;
        localStorage.setItem('psychtrainer_session_id', sessionId); // Persist ID
        await loadSessionsList(); // Refresh sidebar

        // Transition UI
        welcomeScreen.style.display = 'none';
        chatMessages.style.display = 'flex';
        inputBar.style.display = 'flex';

        // Update header
        updatePhase(data.phase);
        phaseBadge.classList.add('active');

        // Show system message
        addMessage('system', data.message);

        // Clear eval placeholder and add initial note
        evalNotes.innerHTML = '';
        addEvalNote('Session started. Observing student\'s approach...', 'neutral');

        // Focus input
        messageInput.focus();

    } catch (err) {
        console.error('Failed to start session:', err);
        btnStart.disabled = false;
        btnStart.innerHTML = '<span class="btn-icon">▶</span> Begin Session';
        addMessage('system', `⚠️ Failed to start: ${err.message}`);
    }
}

async function loadSession(id) {
    if (!id) return;

    try {
        const headers = sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {};
        const res = await fetch(`${API_BASE}/api/session/${id}`, { headers });
        if (!res.ok) throw new Error('Session check failed');
        
        const data = await res.json();
        sessionId = data.session_id;
        localStorage.setItem('psychtrainer_session_id', sessionId);

        // Update active class in sidebar
        document.querySelectorAll('.session-item').forEach(el => {
            el.classList.toggle('active', el.dataset.id === sessionId);
        });

        // Restore UI State
        welcomeScreen.style.display = 'none';
        
        if (data.is_ended && data.grade_report) {
            displayGradeReport(data.grade_report);
            updatePhase('debrief');
            chatMessages.style.display = 'none';
            inputBar.style.display = 'none';
        } else {
            chatMessages.style.display = 'flex';
            inputBar.style.display = 'flex';
            gradeReport.style.display = 'none';
            evalNotes.style.display = 'block';
            updatePhase(data.phase);
            phaseBadge.classList.add('active');
            
            // Restore Messages
            chatMessages.innerHTML = '';
            data.messages.forEach(msg => {
                addMessage(msg.role, msg.content);
            });
            turnCounter.textContent = `Turn ${data.turn_count}`;
            evalNotes.innerHTML = '';
            addEvalNote('Session restored.', 'neutral');
            
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

    } catch (err) {
        console.warn('Could not load session:', err);
    }
}

function newSession() {
    sessionId = null;
    localStorage.removeItem('psychtrainer_session_id');
    
    // Reset UI to Welcome Screen
    welcomeScreen.style.display = 'flex';
    chatMessages.style.display = 'none';
    inputBar.style.display = 'none';
    gradeReport.style.display = 'none';
    evalNotes.style.display = 'block';
    evalNotes.innerHTML = '';
    
    // Reset Header
    phaseBadge.classList.remove('active');
    updatePhase('introduction');
    turnCounter.textContent = 'Turn 0';

    // Remove active state from sidebar
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
    
    // Reset buttons
    btnStart.disabled = false;
    btnStart.innerHTML = '<span class="btn-icon">▶</span> Begin Session';
}

async function loadSessionsList() {
    try {
        const headers = sessionToken ? { 'Authorization': `Bearer ${sessionToken}` } : {};
        const res = await fetch(`${API_BASE}/api/sessions`, { headers });
        if (!res.ok) throw new Error('Failed to fetch sessions');
        const data = await res.json();
        
        sessionList.innerHTML = '';
        data.sessions.forEach(s => {
            const item = document.createElement('div');
            item.className = 'session-item';
            item.dataset.id = s.session_id;
            item.textContent = s.title || `Session: ${s.session_id}`;
            if (s.session_id === sessionId) {
                item.classList.add('active');
            }
            item.onclick = () => loadSession(s.session_id);
            sessionList.appendChild(item);
        });
    } catch (err) {
        console.warn('Could not load sessions list:', err);
    }
}

// Initial Load Logic
async function initApp() {
    await loadSessionsList();
    // User requested ChatGPT style: open on a fresh new conversation
    newSession();
}

// ═══════════════════════════════════════════════════════
//  Chat Logic
// ═══════════════════════════════════════════════════════

async function endSession() {
    if (!sessionId) return;
    if (!confirm('End the session and receive your grade?')) return;

    btnEnd.disabled = true;
    btnEnd.textContent = 'Generating Grade...';
    setInputEnabled(false);

    try {
        const data = await apiPost('/session/end', { session_id: sessionId });
        displayGradeReport(data.report);
        chatMessages.style.display = 'none';
        inputBar.style.display = 'none';
        addMessage('system', '📋 Session ended. Your grade report is ready in the panel →');
        updatePhase('debrief');
        await loadSessionsList(); // Refresh sidebar to show new state
    } catch (err) {
        console.error('Failed to end session:', err);
        addMessage('system', `⚠️ Grading error: ${err.message}`);
        btnEnd.disabled = false;
        btnEnd.textContent = 'End Session & Get Grade';
    }
}

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isWaitingForResponse || !sessionId) return;

    // Add student message to UI
    addMessage('student', text);
    messageInput.value = '';
    autoResizeTextarea();

    isWaitingForResponse = true;
    setInputEnabled(false);
    showTypingIndicator(true);

    let bubbleDiv = null;

    try {
        const headers = { 'Content-Type': 'application/json' };
        if (sessionToken) headers['Authorization'] = `Bearer ${sessionToken}`;
        
        const response = await fetch(`${API_BASE}/api/session/stream_chat`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                session_id: sessionId,
                message: text,
            })
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || 'Request failed');
        }

        showTypingIndicator(false);
        
        // Create an empty patient message bubble
        bubbleDiv = addMessage('patient', '');

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let done = false;
        let buffer = "";

        while (!done) {
            const { value, done: readerDone } = await reader.read();
            if (value) {
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line

                let currentEvent = null;

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
                                  updatePhase(data.phase);
                                  turnCounter.textContent = `Turn ${data.turn_count}`;
                                  if (data.professor_note) {
                                      addEvalNote(data.professor_note);
                                  }
                                  done = true;
                                  break;
                              } else if (currentEvent === 'error') {
                                  throw new Error(data.error);
                              } else {
                                  if (data.token) {
                                      const currentText = bubbleDiv.dataset.text || '';
                                      const newText = currentText + data.token;
                                      bubbleDiv.dataset.text = newText;
                                      bubbleDiv.innerHTML = escapeHtml(newText).replace(/\n/g, '<br>');
                                      chatMessages.scrollTop = chatMessages.scrollHeight;
                                  }
                              }
                         } catch (e) {
                              console.warn("Parse error", e);
                         }
                         currentEvent = null;
                    }
                }
            }
            if (readerDone) {
                done = true;
            }
        }

    } catch (err) {
        showTypingIndicator(false);
        addMessage('system', `⚠️ Error: ${err.message}`);
        if (bubbleDiv && !bubbleDiv.textContent) {
             bubbleDiv.parentElement.remove();
        }
    } finally {
        isWaitingForResponse = false;
        setInputEnabled(true);
        messageInput.focus();
    }
}

// ═══════════════════════════════════════════════════════
//  UI Helpers
// ═══════════════════════════════════════════════════════

function addMessage(role, content) {
    const wrapper = document.createElement('div');
    wrapper.className = `message ${role}`;

    const avatars = {
        patient: '🧑',
        student: '👩‍⚕️',
        system: '🔔',
    };

    wrapper.innerHTML = `
        <div class="message-avatar">${avatars[role] || '💬'}</div>
        <div class="message-bubble"></div>
    `;

    const bubble = wrapper.querySelector('.message-bubble');
    if (content) {
        bubble.dataset.text = content;
        bubble.innerHTML = escapeHtml(content).replace(/\n/g, '<br>');
    } else {
        bubble.dataset.text = "";
    }

    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return bubble;
}

function addEvalNote(text, forceType = null) {
    // Determine note type from content
    let type = forceType || 'neutral';
    if (!forceType) {
        if (text.startsWith('[+]')) type = 'positive';
        else if (text.startsWith('[-]')) type = 'negative';
        else if (text.startsWith('[~]')) type = 'neutral';
    }

    const note = document.createElement('div');
    note.className = `eval-note ${type}`;
    note.textContent = text;

    evalNotes.appendChild(note);
    evalNotes.scrollTop = evalNotes.scrollHeight;
}

function updatePhase(phase) {
    const labels = {
        introduction: '📋 INTRODUCTION',
        examination: '🔍 EXAMINATION',
        diagnosis: '🩺 DIAGNOSIS',
        debrief: '📝 DEBRIEF',
    };
    phaseLabel.textContent = labels[phase] || phase.toUpperCase();
}

function showTypingIndicator(show) {
    typingIndicator.style.display = show ? 'flex' : 'none';
    if (show) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function setInputEnabled(enabled) {
    messageInput.disabled = !enabled;
    btnSend.disabled = !enabled;
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

messageInput.addEventListener('input', autoResizeTextarea);

function toggleSidebar() {
    sidebar.classList.toggle('closed');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ═══════════════════════════════════════════════════════
//  Grade Report Display
// ═══════════════════════════════════════════════════════

function displayGradeReport(report) {
    // Hide eval notes, show grade report
    evalNotes.style.display = 'none';
    gradeReport.style.display = 'block';

    // Score circle
    document.getElementById('grade-letter').textContent = report.letter_grade;
    document.getElementById('grade-score').textContent = `${report.overall_score}/100`;

    // Color the circle based on grade
    const circle = document.getElementById('grade-circle');
    const gradeColors = {
        'A': 'linear-gradient(135deg, #10b981, #059669)',
        'B': 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        'C': 'linear-gradient(135deg, #f59e0b, #d97706)',
        'D': 'linear-gradient(135deg, #ef4444, #dc2626)',
        'F': 'linear-gradient(135deg, #ef4444, #991b1b)',
    };
    circle.style.background = gradeColors[report.letter_grade] || gradeColors['C'];

    // Summary
    document.getElementById('grade-summary').textContent = report.summary;

    // Criteria bars
    const criteriaList = document.getElementById('criteria-list');
    criteriaList.innerHTML = '';

    report.criteria.forEach((c, i) => {
        const pct = (c.score / 10) * 100;
        const color = pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444';

        const item = document.createElement('div');
        item.className = 'criterion-item';
        item.style.animationDelay = `${i * 0.1}s`;

        item.innerHTML = `
            <div class="criterion-header">
                <span class="criterion-name">${escapeHtml(c.criterion)}</span>
                <span class="criterion-score-label">${c.score}/10</span>
            </div>
            <div class="criterion-bar">
                <div class="criterion-fill" style="background: ${color};"></div>
            </div>
            <div class="criterion-feedback">${escapeHtml(c.feedback)}</div>
        `;

        criteriaList.appendChild(item);

        // Animate the bar fill after a short delay
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                item.querySelector('.criterion-fill').style.width = `${pct}%`;
            });
        });
    });

    // Strengths
    const strengthsList = document.getElementById('strengths-list');
    strengthsList.innerHTML = '';
    report.strengths.forEach(s => {
        const li = document.createElement('li');
        li.textContent = s;
        strengthsList.appendChild(li);
    });

    // Improvements
    const improvementsList = document.getElementById('improvements-list');
    improvementsList.innerHTML = '';
    report.improvements.forEach(s => {
        const li = document.createElement('li');
        li.textContent = s;
        improvementsList.appendChild(li);
    });
}
