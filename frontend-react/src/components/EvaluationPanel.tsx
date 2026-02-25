export interface GradeReport {
    letter_grade: string;
    numeric_score: number;
    diagnostic_accuracy: string;
    rapport_and_empathy: string;
    interview_flow_and_risk: string;
    constructive_feedback: string;
}

interface EvaluationPanelProps {
    phase: string;
    turnCount: number;
    notes: string[];
    gradeReport: GradeReport | null;
    onEndSession: () => void;
}

export function EvaluationPanel({ 
    phase, 
    turnCount, 
    notes, 
    gradeReport, 
    onEndSession 
}: EvaluationPanelProps) {
    return (
        <section className="eval-panel">
            <div className="eval-header">
                <div className="title">
                    <span className="icon">📊</span>
                    Live Evaluation
                </div>
                <button 
                    className="btn-end-session" 
                    onClick={onEndSession}
                    disabled={gradeReport !== null}
                >
                    End & Grade
                </button>
            </div>

            <div className="eval-content">
                {gradeReport ? (
                    <div className="grade-report">
                        <div className="grade-header">
                            <div>Final Grade</div>
                            <div className={`grade-badge ${gradeReport.letter_grade.startsWith('A') || gradeReport.letter_grade.startsWith('B') ? 'success' : 'warning'}`}>
                                {gradeReport.letter_grade} ({gradeReport.numeric_score}/100)
                            </div>
                        </div>

                        <div className="grade-section">
                            <strong>Diagnostic Accuracy</strong>
                            <div>{gradeReport.diagnostic_accuracy}</div>
                        </div>

                        <div className="grade-section">
                            <strong>Rapport & Empathy</strong>
                            <div>{gradeReport.rapport_and_empathy}</div>
                        </div>

                        <div className="grade-section">
                            <strong>Interview Flow & Safety Risk</strong>
                            <div>{gradeReport.interview_flow_and_risk}</div>
                        </div>

                        <div className="grade-section">
                            <strong>Constructive Feedback</strong>
                            <div>{gradeReport.constructive_feedback}</div>
                        </div>
                    </div>
                ) : (
                    <div className="eval-notes">
                        {notes.map((note, idx) => (
                            <div key={idx} className="note-card transition-enter">
                                {/* Use basic emoji logic from the legacy app based on the text contents roughly */}
                                <div className="note-badge note-neutral">
                                    {note.includes("Warning") || note.includes("Lost") ? "⚠️ Warning" : "👁️ Observation"}
                                </div>
                                <div className="note-text">{note}</div>
                            </div>
                        ))}
                        {notes.length === 0 && (
                            <div className="note-card" style={{opacity: 0.6}}>
                                <div className="note-badge note-neutral">System</div>
                                <div className="note-text">No notes yet. Start the session...</div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </section>
    );
}
