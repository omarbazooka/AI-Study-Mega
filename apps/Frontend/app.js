// Development & Connection Constants
const API_BASE_URL = "http://localhost:8000";
const DEV_MOCK_USER_ID = "00000000-0000-0000-0000-000000000000";

// Application State
const state = {
    documentId: null,
    documentName: null,
    status: "idle", // idle, uploading, parsing, chunking, embedding, ready, failed
    sessionId: generateSessionId(),
    pollIntervalId: null,
    activeQuiz: null,
    submittingQuiz: false
};

// DOM Elements
const fileInput = document.getElementById("file-input");
const uploadBox = document.getElementById("upload-box");
const fileSelectText = document.getElementById("file-select-text");
const uploadBtn = document.getElementById("upload-btn");
const docNameDisplay = document.getElementById("doc-name-display");
const docStatusDisplay = document.getElementById("doc-status-display");
const docStats = document.getElementById("doc-stats");
const docPages = document.getElementById("doc-pages");
const docChunks = document.getElementById("doc-chunks");
const docDurationContainer = document.getElementById("doc-duration-container");
const docDuration = document.getElementById("doc-duration");
const docErrorDisplay = document.getElementById("doc-error-display");

const summaryBtn = document.getElementById("summary-btn");
const summarySizeSelect = document.getElementById("summary-size");
const customWordCountInput = document.getElementById("custom-word-count");

const quizBtn = document.getElementById("quiz-btn");
const quizDifficultySelect = document.getElementById("quiz-difficulty");
const quizCountSelect = document.getElementById("quiz-questions-count");

const authTokenInput = document.getElementById("auth-token");

const chatHeaderTitle = document.getElementById("chat-header-title");
const langSelect = document.getElementById("lang-select");
const messagesArea = document.getElementById("messages-area");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");

const progressPanel = document.getElementById("progress-panel");
const progressBar = document.getElementById("progress-bar");
const progressMsg = document.getElementById("progress-message");
const progressStages = document.getElementById("progress-stages");

// Initialize auth token
authTokenInput.value = localStorage.getItem("supabase_token") || "";
authTokenInput.addEventListener("input", () => {
    localStorage.setItem("supabase_token", authTokenInput.value.trim());
});

// Summary target size toggle
summarySizeSelect.addEventListener("change", () => {
    if (summarySizeSelect.value === "custom") {
        customWordCountInput.style.display = "block";
    } else {
        customWordCountInput.style.display = "none";
    }
});

// Generate Session UUID
function generateSessionId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0,
            v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Request Headers Helper
function getHeaders() {
    const headers = {
        "Content-Type": "application/json"
    };
    const token = (authTokenInput.value || localStorage.getItem("supabase_token") || "").trim();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
}

// Drag & Drop listeners
uploadBox.addEventListener("click", () => {
    if (!["uploading", "parsing", "chunking", "embedding"].includes(state.status)) {
        fileInput.click();
    }
});

uploadBox.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadBox.style.borderColor = "#6200ee";
});

uploadBox.addEventListener("dragleave", () => {
    uploadBox.style.borderColor = "#444";
});

uploadBox.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadBox.style.borderColor = "#444";
    if (["uploading", "parsing", "chunking", "embedding"].includes(state.status)) {
        return;
    }
    if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        handleFileSelection();
    }
});

fileInput.addEventListener("change", handleFileSelection);

function handleFileSelection() {
    const file = fileInput.files[0];
    if (file) {
        if (file.type !== "application/pdf") {
            showError("Only PDF files are supported.");
            uploadBtn.disabled = true;
            fileSelectText.textContent = "Choose a PDF file";
            return;
        }
        fileSelectText.textContent = `${file.name} (${formatBytes(file.size)})`;
        uploadBtn.disabled = false;
        hideError();
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

uploadBtn.addEventListener("click", uploadFile);

async function uploadFile() {
    const file = fileInput.files[0];
    if (!file) return;

    updateUIStatus("uploading");
    uploadBtn.disabled = true;
    docNameDisplay.textContent = file.name;
    state.documentName = file.name;

    const formData = new FormData();
    formData.append("file", file);

    const headers = {};
    const token = (authTokenInput.value || localStorage.getItem("supabase_token") || "").trim();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
            method: "POST",
            headers: headers,
            body: formData
        });

        if (response.status === 401) {
            throw new Error("Authentication token is expired or invalid. Please paste a new token.");
        }

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to upload document.");
        }

        const data = await response.json();
        state.documentId = data.document_id;
        updateUIStatus(data.status);
        startStatusPolling(data.document_id);

    } catch (error) {
        updateUIStatus("failed", { error_message: error.message });
        uploadBtn.disabled = false;
    }
}

function startStatusPolling(documentId) {
    if (state.pollIntervalId) {
        clearInterval(state.pollIntervalId);
    }

    state.pollIntervalId = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/status`, {
                headers: getHeaders()
            });
            
            if (response.status === 401) {
                throw new Error("Authentication token is expired or invalid.");
            }

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Failed to retrieve status.");
            }

            const data = await response.json();
            updateUIStatus(data.status, data);

            if (data.status === "ready" || data.status === "failed") {
                clearInterval(state.pollIntervalId);
                state.pollIntervalId = null;
            }

        } catch (error) {
            clearInterval(state.pollIntervalId);
            state.pollIntervalId = null;
            updateUIStatus("failed", { error_message: "Polling error: " + error.message });
        }
    }, 2000);
}

function updateUIStatus(newStatus, extraData = {}) {
    state.status = newStatus.toLowerCase();
    docStatusDisplay.className = `status-badge status-${state.status}`;
    docStatusDisplay.textContent = state.status.toUpperCase();

    if (extraData.processing_time_seconds !== undefined && extraData.processing_time_seconds !== null) {
        docDurationContainer.style.display = "block";
        docDuration.textContent = `${extraData.processing_time_seconds}s`;
    } else {
        docDurationContainer.style.display = "none";
    }

    if (state.status === "ready") {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        summaryBtn.disabled = false;
        quizBtn.disabled = false;
        chatInput.placeholder = "Ask a question about the document...";
        chatHeaderTitle.textContent = state.documentName;
        
        docStats.style.display = "block";
        docPages.textContent = extraData.page_count || "N/A";
        docChunks.textContent = extraData.chunk_count || 0;
        
        appendSystemMessage("Document is ready! You can now start chatting or generate summaries/quizzes.");
        uploadBtn.disabled = false;
    } else if (state.status === "failed") {
        chatInput.disabled = true;
        sendBtn.disabled = true;
        summaryBtn.disabled = true;
        quizBtn.disabled = true;
        chatInput.placeholder = "Upload failed. Please try again.";
        
        const errMsg = extraData.error_message || "Ingestion pipeline failed.";
        showError(errMsg);
        appendSystemMessage(`Error: ${errMsg}`);
        uploadBtn.disabled = false;
    } else {
        chatInput.disabled = true;
        sendBtn.disabled = true;
        summaryBtn.disabled = true;
        quizBtn.disabled = true;
        chatInput.placeholder = `Ingestion pipeline status: ${state.status.toUpperCase()}...`;
        docStats.style.display = "none";
    }
}

chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text || !state.documentId || state.status !== "ready") return;

    chatInput.value = "";
    sendMessage(text);
});

// Chat QA Stream Reader (POST to /chat/stream)
async function sendMessage(text) {
    appendMessage("user", text);
    const typingIndicator = appendTypingIndicator();
    
    // Display progress panel
    progressPanel.style.display = "block";
    progressBar.style.width = "0%";
    progressMsg.textContent = "Initializing stream...";
    progressStages.innerHTML = "";

    try {
        const payload = {
            user_id: DEV_MOCK_USER_ID,
            session_id: state.sessionId,
            message: text,
            language: langSelect.value,
            user_level: "intermediate",
            request_source: "chat"
        };

        const response = await fetch(`${API_BASE_URL}/api/v1/documents/${state.documentId}/chat/stream`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });

        removeTypingIndicator(typingIndicator);

        if (response.status === 401) {
            throw new Error("Session or authentication token has expired. Please paste a fresh token.");
        }
        if (response.status === 403) {
            throw new Error("Permission denied. You do not have access to this document.");
        }
        if (!response.ok) {
            throw new Error("Failed to connect progress stream: " + response.statusText);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (line.trim()) {
                    const event = JSON.parse(line);
                    progressBar.style.width = `${event.progress}%`;
                    progressMsg.textContent = event.message;

                    const li = document.createElement("li");
                    li.innerHTML = `<strong>[${event.stage.toUpperCase()}]</strong> ${event.message} (${event.status})`;
                    progressStages.appendChild(li);
                    progressStages.scrollTop = progressStages.scrollHeight;

                    if (event.stage === "completed" && event.status === "completed") {
                        appendMessage("assistant", event.content, event.citations || []);
                    }
                    if (event.status === "failed") {
                        appendMessage("assistant", `System Error: ${event.message}`);
                        return;
                    }
                }
            }
        }

    } catch (error) {
        removeTypingIndicator(typingIndicator);
        appendMessage("assistant", `System Error: ${error.message}`);
    } finally {
        setTimeout(() => {
            progressPanel.style.display = "none";
        }, 3000);
    }
}

// Map-Reduce Summarize Handler
summaryBtn.addEventListener("click", async () => {
    if (!state.documentId || state.status !== "ready") return;
    
    appendSystemMessage("Requesting Map-Reduce summary...");
    const typingIndicator = appendTypingIndicator();

    const summarySize = summarySizeSelect.value;
    const targetWordCount = summarySize === "custom" ? parseInt(customWordCountInput.value) || 100 : null;

    try {
        const payload = {
            user_id: DEV_MOCK_USER_ID,
            session_id: state.sessionId,
            language: langSelect.value,
            user_level: "intermediate",
            summary_style: "bullet_points",
            summary_size: summarySize,
            target_word_count: targetWordCount
        };

        const response = await fetch(`${API_BASE_URL}/api/v1/documents/${state.documentId}/summary`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });

        removeTypingIndicator(typingIndicator);

        if (response.status === 401) {
            throw new Error("Authentication token is expired or invalid.");
        }

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to generate summary.");
        }

        const data = await response.json();
        appendMessage("assistant", data.message, data.citations, data.pipeline_trace);

    } catch (error) {
        removeTypingIndicator(typingIndicator);
        appendMessage("assistant", `System Error generating summary: ${error.message}`);
    }
});

// Map-Reduce Quiz Generation Handler
quizBtn.addEventListener("click", async () => {
    if (!state.documentId || state.status !== "ready") return;

    appendSystemMessage("Generating interactive quiz...");
    const typingIndicator = appendTypingIndicator();

    const difficulty = quizDifficultySelect.value;
    const count = parseInt(quizCountSelect.value) || 5;

    try {
        const payload = {
            user_id: DEV_MOCK_USER_ID,
            session_id: state.sessionId,
            language: langSelect.value,
            user_level: "intermediate",
            difficulty: difficulty,
            number_of_questions: count,
            question_type: "multiple_choice"
        };

        const response = await fetch(`${API_BASE_URL}/api/v1/documents/${state.documentId}/quiz`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });

        removeTypingIndicator(typingIndicator);

        if (response.status === 401) {
            throw new Error("Authentication token is expired or invalid.");
        }

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to generate quiz.");
        }

        const data = await response.json();
        const quizObj = JSON.parse(data.message);
        renderInteractiveQuiz(quizObj);

    } catch (error) {
        removeTypingIndicator(typingIndicator);
        appendMessage("assistant", `System Error generating quiz: ${error.message}`);
    }
});

// Render Interactive Quiz Layout
function renderInteractiveQuiz(quizData) {
    state.activeQuiz = quizData;
    
    const welcome = messagesArea.querySelector(".welcome-message");
    if (welcome) {
        messagesArea.removeChild(welcome);
    }
    
    const quizDiv = document.createElement("div");
    quizDiv.className = "quiz-card";
    quizDiv.id = `quiz-${quizData.quiz_id}`;
    
    let quizHTML = `<div class="quiz-title">📝 ${quizData.title || "Interactive Quiz"}</div>`;
    
    quizData.questions.forEach((q, idx) => {
        quizHTML += `
            <div class="quiz-question" id="quiz-q-${q.id}">
                <div class="quiz-question-text" style="font-weight: bold; margin-bottom: 8px;">${idx + 1}. ${q.question_text}</div>
                <div class="quiz-options" style="display: flex; flex-direction: column; gap: 6px;">
        `;
        q.options.forEach((opt, optIdx) => {
            quizHTML += `
                <label class="quiz-option-label" for="opt-${q.id}-${optIdx}">
                    <input type="radio" name="quiz-ans-${q.id}" id="opt-${q.id}-${optIdx}" value="${optIdx}">
                    <span style="margin-left: 6px;">${opt}</span>
                </label>
            `;
        });
        quizHTML += `
                </div>
            </div>
        `;
    });
    
    quizHTML += `
        <button id="submit-quiz-btn" class="quiz-submit-btn" style="width: 100%; margin-top: 10px;">Submit Answers</button>
        <p id="quiz-error-text" class="error-text" style="display: none; color: #f44336; margin-top: 5px;"></p>
    `;
    
    quizDiv.innerHTML = quizHTML;
    messagesArea.appendChild(quizDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
    
    // Bind submission listener
    document.getElementById("submit-quiz-btn").addEventListener("click", () => {
        submitQuizAnswers(quizData.quiz_id);
    });
}

// Grade Quiz Answers Server-Side with Idempotency
async function submitQuizAnswers(quizId) {
    if (state.submittingQuiz) return;
    
    const submitBtn = document.getElementById("submit-quiz-btn");
    const errorText = document.getElementById("quiz-error-text");
    
    const responses = [];
    const questions = state.activeQuiz.questions;
    let allAnswered = true;
    
    for (const q of questions) {
        const selected = document.querySelector(`input[name="quiz-ans-${q.id}"]:checked`);
        if (!selected) {
            allAnswered = false;
            break;
        }
        responses.push({
            question_id: q.id,
            selected_option_id: parseInt(selected.value)
        });
    }
    
    if (!allAnswered) {
        errorText.textContent = "Please answer all questions before submitting.";
        errorText.style.display = "block";
        return;
    }
    
    errorText.style.display = "none";
    submitBtn.disabled = true;
    submitBtn.textContent = "Grading answers on server...";
    state.submittingQuiz = true;

    // Unique Idempotency Key
    const idempotencyKey = `attempt-${state.sessionId}-${quizId}`;

    try {
        const payload = {
            attempt_number: 1,
            idempotency_key: idempotencyKey,
            responses: responses
        };

        const response = await fetch(`${API_BASE_URL}/api/v1/documents/quizzes/${quizId}/submit`, {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });

        if (response.status === 401) {
            throw new Error("Authentication token has expired. Please paste a new token.");
        }

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Submission grading failed.");
        }

        const graded = await response.json();
        
        // Lock options inputs
        document.querySelectorAll(`input[name^="quiz-ans-"]`).forEach(i => i.disabled = true);
        
        // Apply visual reviews (correct/incorrect) and append explanations
        graded.responses.forEach(r => {
            const questionDiv = document.getElementById(`quiz-q-${r.question_id}`);
            
            r.options.forEach((opt, optIdx) => {
                const label = document.querySelector(`label[for="opt-${r.question_id}-${optIdx}"]`);
                if (optIdx === r.correct_option_id) {
                    label.className = "quiz-option-label correct";
                } else if (optIdx === r.selected_option_id && !r.is_correct) {
                    label.className = "quiz-option-label incorrect";
                }
            });
            
            const explDiv = document.createElement("div");
            explDiv.className = "quiz-explanation";
            explDiv.innerHTML = `<strong>Correct Answer:</strong> Option ${r.correct_option_id + 1} | <strong>Explanation:</strong> ${r.explanation}`;
            questionDiv.appendChild(explDiv);
        });
        
        // Render score
        submitBtn.textContent = `Grading Completed! Score: ${graded.score_percentage}% (${graded.correct_count}/${graded.total_questions})`;
        submitBtn.style.backgroundColor = "#4caf50";

    } catch (error) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit Answers";
        errorText.textContent = error.message;
        errorText.style.display = "block";
    } finally {
        state.submittingQuiz = false;
    }
}

// Render Messages & Citations
function appendMessage(role, content, citations = [], pipelineTrace = null) {
    const welcome = messagesArea.querySelector(".welcome-message");
    if (welcome) {
        messagesArea.removeChild(welcome);
    }

    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${role}`;
    
    // Auto RTL basic regex
    const isArabic = /[\u0600-\u06FF]/.test(content);
    if (isArabic) {
        messageDiv.classList.add("rtl-text");
    }

    let finalHTML = "";

    if (pipelineTrace) {
        // Pipeline trace metadata rendering logic preserved for tracing detail
        const planner = pipelineTrace.planner || {};
        const orchestrator = pipelineTrace.orchestrator || {};
        const memory = pipelineTrace.memory || {};
        const retrieval = pipelineTrace.retrieval || {};
        const tasksList = (planner.tasks || []).map(t => `<li><strong>Task:</strong> ${t.type} | <strong>Query:</strong> "${t.query}"</li>`).join("");

        finalHTML += `
            <div class="pipeline-trace-container" style="background: #111; padding: 10px; border-radius: 4px; margin-bottom: 10px; font-size: 0.8rem; border-left: 2px solid #ff9800;">
                <div class="pipeline-trace-header" style="font-weight: bold; color: #ff9800; margin-bottom: 8px;">🔍 PROCESS TRACE STAGES</div>
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <div><strong>Planner status:</strong> ${planner.status || "completed"} | <strong>Execution mode:</strong> ${planner.execution_mode || "single"}</div>
                    <div><strong>Orchestrator:</strong> ${orchestrator.selected_execution_mode || "single"} | <strong>Verifier status:</strong> ${orchestrator.verifier_status || "not_run"}</div>
                    <div><strong>Memory items retrieved:</strong> ${memory.retrieved_count || 0}</div>
                    <div><strong>Retrieval RAG status:</strong> ${retrieval.status || "not_run"} | <strong>Latency:</strong> ${retrieval.latency_ms || 0}ms</div>
                    ${tasksList ? `<ul style="margin-left: 15px; margin-top: 5px;">${tasksList}</ul>` : ""}
                </div>
            </div>
            <hr style="border: none; border-top: 1px dashed #444; margin: 10px 0;">
        `;
    }

    // Add content body text
    finalHTML += `<div class="message-text" style="white-space: pre-wrap;">${content}</div>`;

    // Render citations
    if (citations && citations.length > 0) {
        let citationHTML = `
            <div class="citations-container" style="margin-top: 10px; padding-top: 8px; border-top: 1px dashed #444; font-size: 0.8rem; color: #aaa;">
                <strong>Citations:</strong>
                <ul style="list-style: none; padding-left: 0; display: flex; flex-direction: column; gap: 4px; margin-top: 4px;">
        `;
        citations.forEach((c, idx) => {
            citationHTML += `
                <li>[${idx + 1}] Chk: ${c.chunk_id.substring(0, 8)}... | Page: ${c.page_number} | Relevance: ${c.score ? Math.round(c.score * 100) + '%' : 'N/A'}</li>
            `;
        });
        citationHTML += `
                </ul>
            </div>
        `;
        finalHTML += citationHTML;
    }

    messageDiv.innerHTML = finalHTML;
    messagesArea.appendChild(messageDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

function appendSystemMessage(text) {
    const sysDiv = document.createElement("div");
    sysDiv.className = "system-notification";
    sysDiv.style.cssText = "text-align: center; color: #777; font-size: 0.8rem; margin: 5px 0;";
    sysDiv.textContent = `[SYSTEM] ${text}`;
    messagesArea.appendChild(sysDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

function appendTypingIndicator() {
    const welcome = messagesArea.querySelector(".welcome-message");
    if (welcome) {
        messagesArea.removeChild(welcome);
    }

    const indicator = document.createElement("div");
    indicator.className = "message assistant typing";
    indicator.innerHTML = `<span class="typing-dot">.</span><span class="typing-dot">.</span><span class="typing-dot">.</span>`;
    messagesArea.appendChild(indicator);
    messagesArea.scrollTop = messagesArea.scrollHeight;
    return indicator;
}

function removeTypingIndicator(indicator) {
    if (indicator && indicator.parentNode === messagesArea) {
        messagesArea.removeChild(indicator);
    }
}

function showError(message) {
    docErrorDisplay.style.display = "block";
    docErrorDisplay.textContent = message;
}

function hideError() {
    docErrorDisplay.style.display = "none";
    docErrorDisplay.textContent = "";
}
