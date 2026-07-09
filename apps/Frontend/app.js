// Development & Connection Constants
const API_BASE_URL = "http://localhost:8000";
const DEV_MOCK_USER_ID = "00000000-0000-0000-0000-000000000000";

// Application State
const state = {
    documentId: null,
    documentName: null,
    status: "idle", // idle, uploading, parsing, chunking, embedding, ready, failed
    sessionId: generateSessionId(),
    pollIntervalId: null
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
const quizBtn = document.getElementById("quiz-btn");
const chatHeaderTitle = document.getElementById("chat-header-title");
const langSelect = document.getElementById("lang-select");
const messagesArea = document.getElementById("messages-area");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");

// Generate a random unique session identifier (RFC 4122 compliant UUID v4)
function generateSessionId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0,
            v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Drag & Drop event listeners
uploadBox.addEventListener("click", () => {
    if (state.status !== "uploading" && state.status !== "parsing" && state.status !== "chunking" && state.status !== "embedding") {
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
    if (state.status === "uploading" || state.status === "parsing" || state.status === "chunking" || state.status === "embedding") {
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

// Format bytes to readable size
function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

// Trigger Document Upload
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

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to upload document.");
        }

        const data = await response.json();
        state.documentId = data.document_id;
        
        // Show status based on immediate upload response status
        updateUIStatus(data.status);
        
        // Start polling the status endpoint
        startStatusPolling(data.document_id);

    } catch (error) {
        updateUIStatus("failed", { error_message: error.message });
        uploadBtn.disabled = false;
    }
}

// Poll Ingestion Status
function startStatusPolling(documentId) {
    if (state.pollIntervalId) {
        clearInterval(state.pollIntervalId);
    }

    state.pollIntervalId = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/status`);
            
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

// Update UI depending on Pipeline Status
function updateUIStatus(newStatus, extraData = {}) {
    state.status = newStatus.toLowerCase();
    
    // Update badge class and text
    docStatusDisplay.className = `status-badge status-${state.status}`;
    docStatusDisplay.textContent = state.status.toUpperCase();

    // Show duration if available in extraData
    if (extraData.processing_time_seconds !== undefined && extraData.processing_time_seconds !== null) {
        docDurationContainer.style.display = "block";
        docDuration.textContent = `${extraData.processing_time_seconds}s`;
    } else {
        docDurationContainer.style.display = "none";
    }

    if (state.status === "ready") {
        // Unlock controls
        chatInput.disabled = false;
        sendBtn.disabled = false;
        summaryBtn.disabled = false;
        quizBtn.disabled = false;
        chatInput.placeholder = "Ask a question about the document...";
        chatHeaderTitle.textContent = state.documentName;
        
        // Display statistics
        docStats.style.display = "block";
        docPages.textContent = extraData.page_count || "N/A";
        docChunks.textContent = extraData.chunk_count || 0;
        
        // Let the user know the document is ready
        appendSystemMessage("Document is ready! You can now start chatting or generate summaries/quizzes.");
        uploadBtn.disabled = false; // allow uploading another document
    } else if (state.status === "failed") {
        // Lock controls
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
        // Processing (uploading, parsing, chunking, embedding)
        chatInput.disabled = true;
        sendBtn.disabled = true;
        summaryBtn.disabled = true;
        quizBtn.disabled = true;
        chatInput.placeholder = `Ingestion pipeline status: ${state.status.toUpperCase()}...`;
        
        // Hide stats during ingestion
        docStats.style.display = "none";
    }
}

// Send Message Handler
chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text || !state.documentId || state.status !== "ready") return;

    chatInput.value = "";
    sendMessage(text);
});

async function sendMessage(text) {
    appendMessage("user", text);
    
    const typingIndicator = appendTypingIndicator();

    try {
        const payload = {
            user_id: DEV_MOCK_USER_ID,
            session_id: state.sessionId,
            message: text,
            language: langSelect.value,
            user_level: "intermediate",
            request_source: "chat"
        };

        const response = await fetch(`${API_BASE_URL}/api/v1/documents/${state.documentId}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        removeTypingIndicator(typingIndicator);

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to send chat message.");
        }

        const data = await response.json();
        // The API returns AIResponse which has a message property containing the answer
        appendMessage("assistant", data.message, data.citations, data.pipeline_trace);

    } catch (error) {
        removeTypingIndicator(typingIndicator);
        appendMessage("assistant", `System Error: ${error.message}`);
    }
}

// Summarize Tool Handler
summaryBtn.addEventListener("click", async () => {
    if (!state.documentId || state.status !== "ready") return;
    
    appendSystemMessage("Requesting document summary...");
    const typingIndicator = appendTypingIndicator();

    try {
        const payload = {
            user_id: DEV_MOCK_USER_ID,
            session_id: state.sessionId,
            language: langSelect.value,
            user_level: "intermediate",
            summary_style: "bullet_points"
        };

        const response = await fetch(`${API_BASE_URL}/api/v1/documents/${state.documentId}/summary`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        removeTypingIndicator(typingIndicator);

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

// Quiz Tool Handler
quizBtn.addEventListener("click", async () => {
    if (!state.documentId || state.status !== "ready") return;

    appendSystemMessage("Requesting quiz generation...");
    const typingIndicator = appendTypingIndicator();

    try {
        const payload = {
            user_id: DEV_MOCK_USER_ID,
            session_id: state.sessionId,
            language: langSelect.value,
            user_level: "intermediate",
            difficulty: "medium",
            number_of_questions: 5,
            question_type: "multiple_choice"
        };

        const response = await fetch(`${API_BASE_URL}/api/v1/documents/${state.documentId}/quiz`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        removeTypingIndicator(typingIndicator);

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to generate quiz.");
        }

        const data = await response.json();
        appendMessage("assistant", data.message, data.citations, data.pipeline_trace);

    } catch (error) {
        removeTypingIndicator(typingIndicator);
        appendMessage("assistant", `System Error generating quiz: ${error.message}`);
    }
});

// Render Message bubble in Chat List
function appendMessage(role, content, citations = [], pipelineTrace = null) {
    // Check and remove the welcome screen if present
    const welcome = messagesArea.querySelector(".welcome-message");
    if (welcome) {
        messagesArea.removeChild(welcome);
    }

    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${role}`;
    
    // Check text direction for Arabic rendering (basic regex checking for Arabic characters)
    const isArabic = /[\u0600-\u06FF]/.test(content);
    if (isArabic) {
        messageDiv.classList.add("rtl-text");
    }

    let finalHTML = "";

    // Render pipeline_trace if present
    if (pipelineTrace) {
        const planner = pipelineTrace.planner || {};
        const orchestrator = pipelineTrace.orchestrator || {};
        const memory = pipelineTrace.memory || {};
        const retrieval = pipelineTrace.retrieval || {};

        const tasksList = (planner.tasks || []).map(t => `<li><strong>المهمة:</strong> ${t.type} | <strong>الاستعلام:</strong> "${t.query}"</li>`).join("");
        const selectedPipelines = (orchestrator.selected_pipeline_names || []).join(", ") || "none";
        const launchedTasks = (orchestrator.launched_task_names || []).join(", ") || "none";

        let personalizationText = "Not Applied";
        if (memory.personalization_applied) {
            if (memory.retrieved_count === 0) {
                personalizationText = `Applied from default ${memory.profile_level || 'beginner'} profile`;
            } else {
                personalizationText = "Applied from retrieved memories";
            }
        }

        finalHTML += `
            <div class="pipeline-trace-container">
                <div class="pipeline-trace-header">🔍 تفاصيل مراحل المعالجة (Pipeline Trace)</div>
                <div class="pipeline-trace-sections">
                    <div class="trace-section planner-trace">
                        <h4>📋 المخطط (Planner)</h4>
                        <ul>
                            <li><strong>Status:</strong> ${planner.status || "completed"}</li>
                            <li><strong>Mode:</strong> ${planner.mode || "rule_based"}</li>
                            <li><strong>LLM Used:</strong> ${planner.llm_used ? "true" : "false"}</li>
                            <li><strong>Intent:</strong> ${planner.intent || "unknown"}</li>
                            <li><strong>Execution Mode:</strong> ${planner.execution_mode || "single"}</li>
                            <li><strong>Confidence:</strong> ${(planner.confidence || 0) * 100}%</li>
                            ${tasksList ? `<li><strong>Planned Tasks:</strong><ul>${tasksList}</ul></li>` : ""}
                        </ul>
                    </div>
                    <div class="trace-section orchestrator-trace">
                        <h4>⚙️ المنسق (Orchestrator)</h4>
                        <ul>
                            <li><strong>Status:</strong> ${orchestrator.status || "routed_only"}</li>
                            <li><strong>Selected Execution Mode:</strong> ${orchestrator.selected_execution_mode || "single"}</li>
                            <li><strong>Selected Pipeline Names:</strong> ${selectedPipelines}</li>
                            <li><strong>DAG Mode:</strong> ${orchestrator.dag_mode || "not_used"}</li>
                            <li><strong>Parallel/Sequential Status:</strong> ${orchestrator.parallel_sequential_hybrid_status || "sequential"}</li>
                            <li><strong>Launched Task Names:</strong> ${launchedTasks}</li>
                            <li><strong>Retrieval Status:</strong> ${orchestrator.retrieval_status || "not_run"}</li>
                            <li><strong>Verifier Status:</strong> ${orchestrator.verifier_status || "not_run"}</li>
                        </ul>
                    </div>
                    <div class="trace-section memory-trace">
                        <h4>🧠 الذاكرة (Memory)</h4>
                        <ul>
                            <li><strong>Memory Layer:</strong> ${memory.memory_layer_checked ? "Checked" : "Not Checked"}</li>
                            <li><strong>Long-term Memories Retrieved:</strong> ${memory.retrieved_count || 0}</li>
                            <li><strong>Personalization:</strong> ${personalizationText}</li>
                        </ul>
                    </div>
                    <div class="trace-section retrieval-trace">
                        <h4>🔍 الاسترجاع (Retrieval RAG)</h4>
                        <ul>
                            <li><strong>Status:</strong> ${retrieval.status || "not_run"}</li>
                            <li><strong>Confidence:</strong> ${Math.round((retrieval.confidence || 0) * 100)}%</li>
                            <li><strong>Chunks Sourced:</strong> ${retrieval.chunks_used || 0}</li>
                            <li><strong>Latency:</strong> ${retrieval.latency_ms || 0}ms</li>
                        </ul>
                    </div>
                </div>
            </div>
            <hr class="trace-divider">
        `;
    }

    // Format content with custom simple markdown rendering
    const formattedHTML = formatMarkdown(content);
    finalHTML += `<div class="final-answer-container">${formattedHTML}</div>`;
    messageDiv.innerHTML = finalHTML;

    // Render citations if present
    if (citations && citations.length > 0) {
        const citationsDiv = document.createElement("div");
        citationsDiv.className = "citations-container";
        citationsDiv.innerHTML = "<strong>Sources:</strong> ";
        
        citations.forEach(cit => {
            const badge = document.createElement("span");
            badge.className = "citation-badge";
            
            let label = `Page ${cit.page_number}`;
            if (cit.section_title) {
                label += `: ${cit.section_title}`;
            }
            if (cit.score) {
                label += ` (conf: ${Math.round(cit.score * 100)}%)`;
            }
            badge.textContent = label;
            citationsDiv.appendChild(badge);
        });
        messageDiv.appendChild(citationsDiv);
    }

    messagesArea.appendChild(messageDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

// Append System Message
function appendSystemMessage(text) {
    appendMessage("system", text);
}

// Loading typing state indicator helpers
function appendTypingIndicator() {
    const indicator = document.createElement("div");
    indicator.className = "message assistant";
    
    indicator.innerHTML = `
        <div class="stages-loader">
            <div class="stage-item" id="stage-planner">
                <span class="stage-icon loader-circle"></span>
                <span class="stage-text">تحليل السؤال والتخطيط (Planner)...</span>
            </div>
            <div class="stage-item pending" id="stage-retriever">
                <span class="stage-icon dot"></span>
                <span class="stage-text">استرجاع قطع المستند (Retriever)...</span>
            </div>
            <div class="stage-item pending" id="stage-executor">
                <span class="stage-icon dot"></span>
                <span class="stage-text">توليد وصياغة الإجابة (Executor)...</span>
            </div>
            <div class="stage-item pending" id="stage-verifier">
                <span class="stage-icon dot"></span>
                <span class="stage-text">التحقق وتدقيق الجودة (Verifier)...</span>
            </div>
        </div>
    `;
    
    messagesArea.appendChild(indicator);
    messagesArea.scrollTop = messagesArea.scrollHeight;

    // Simulate progress transitions
    const t1 = setTimeout(() => {
        const planner = indicator.querySelector("#stage-planner");
        const retriever = indicator.querySelector("#stage-retriever");
        if (planner && retriever) {
            planner.classList.remove("loading");
            planner.classList.add("done");
            planner.querySelector(".stage-icon").className = "stage-icon done-check";
            planner.querySelector(".stage-icon").innerHTML = "✓";
            
            retriever.classList.remove("pending");
            retriever.classList.add("loading");
            retriever.querySelector(".stage-icon").className = "stage-icon loader-circle";
        }
    }, 600);

    const t2 = setTimeout(() => {
        const retriever = indicator.querySelector("#stage-retriever");
        const executor = indicator.querySelector("#stage-executor");
        if (retriever && executor) {
            retriever.classList.remove("loading");
            retriever.classList.add("done");
            retriever.querySelector(".stage-icon").className = "stage-icon done-check";
            retriever.querySelector(".stage-icon").innerHTML = "✓";
            
            executor.classList.remove("pending");
            executor.classList.add("loading");
            executor.querySelector(".stage-icon").className = "stage-icon loader-circle";
        }
    }, 1200);

    const t3 = setTimeout(() => {
        const executor = indicator.querySelector("#stage-executor");
        const verifier = indicator.querySelector("#stage-verifier");
        if (executor && verifier) {
            executor.classList.remove("loading");
            executor.classList.add("done");
            executor.querySelector(".stage-icon").className = "stage-icon done-check";
            executor.querySelector(".stage-icon").innerHTML = "✓";
            
            verifier.classList.remove("pending");
            verifier.classList.add("loading");
            verifier.querySelector(".stage-icon").className = "stage-icon loader-circle";
        }
    }, 1800);

    indicator.dataset.timer1 = t1;
    indicator.dataset.timer2 = t2;
    indicator.dataset.timer3 = t3;

    return indicator;
}

function removeTypingIndicator(indicatorElement) {
    if (indicatorElement) {
        if (indicatorElement.dataset.timer1) clearTimeout(parseInt(indicatorElement.dataset.timer1));
        if (indicatorElement.dataset.timer2) clearTimeout(parseInt(indicatorElement.dataset.timer2));
        if (indicatorElement.dataset.timer3) clearTimeout(parseInt(indicatorElement.dataset.timer3));
        if (indicatorElement.parentNode) {
            indicatorElement.parentNode.removeChild(indicatorElement);
        }
    }
}

// Simple Markdown to HTML parser
function formatMarkdown(text) {
    if (!text) return "";
    
    const lines = text.split("\n");
    let html = "";
    let inList = false;
    
    for (let line of lines) {
        // Escape HTML tags to prevent injections but preserve formatting
        let cleanLine = line
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
        // Inline bold (**text**)
        cleanLine = cleanLine.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        // Inline italic (*text*)
        cleanLine = cleanLine.replace(/\*(.*?)\*/g, "<em>$1</em>");
        
        // Horizontal Rule
        if (cleanLine.trim() === "---") {
            if (inList) { html += "</ul>"; inList = false; }
            html += "<hr>";
        }
        // Headers
        else if (cleanLine.startsWith("### ")) {
            if (inList) { html += "</ul>"; inList = false; }
            html += `<h3>${cleanLine.substring(4)}</h3>`;
        } else if (cleanLine.startsWith("## ")) {
            if (inList) { html += "</ul>"; inList = false; }
            html += `<h2>${cleanLine.substring(3)}</h2>`;
        } else if (cleanLine.startsWith("# ")) {
            if (inList) { html += "</ul>"; inList = false; }
            html += `<h1>${cleanLine.substring(2)}</h1>`;
        } 
        // List items
        else if (cleanLine.trim().startsWith("- ") || cleanLine.trim().startsWith("* ")) {
            if (!inList) { html += "<ul>"; inList = true; }
            const content = cleanLine.trim().substring(2);
            html += `<li>${content}</li>`;
        } 
        // Normal paragraph/empty line
        else {
            if (inList) { html += "</ul>"; inList = false; }
            if (cleanLine.trim() === "") {
                html += "<br>";
            } else {
                html += `<p>${cleanLine}</p>`;
            }
        }
    }
    if (inList) { html += "</ul>"; }
    return html;
}

// Visual error toast wrappers
function showError(message) {
    docErrorDisplay.textContent = message;
    docErrorDisplay.style.display = "block";
}

function hideError() {
    docErrorDisplay.textContent = "";
    docErrorDisplay.style.display = "none";
}
