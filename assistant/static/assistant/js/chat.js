/**
 * MIICiQ — Chat Interface Client Logic
 * Implements SSE streaming, light-dismiss modals, feedback, and session history
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const chatMessagesList = document.getElementById('chatMessagesList');
  const chatContainer = document.getElementById('chatContainer');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  const welcomeScreen = document.getElementById('welcomeScreen');
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const sidebar = document.getElementById('sidebar');
  const activeSessionInput = document.getElementById('activeSessionId');
  const sourceModal = document.getElementById('sourceModal');
  const modalViewDocumentLink = document.getElementById('modalViewDocumentLink');
  const feedbackModal = document.getElementById('feedbackModal');

  // Modern Web Guidance: Setup light-dismiss fallback for all <dialog> elements
  const allDialogs = document.querySelectorAll('dialog');
  allDialogs.forEach((dialog) => {
    if (!('closedBy' in HTMLDialogElement.prototype)) {
      dialog.addEventListener('click', (event) => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const isDialogContent = (
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width
        );
        if (isDialogContent) return;
        dialog.close();
      });
    }
  });

  // Mobile drawer toggle
  if (mobileMenuBtn && sidebar) {
    mobileMenuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }

  // Auto-resize textarea
  if (chatInput) {
    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
      if (sendBtn) {
        sendBtn.disabled = !chatInput.value.trim();
      }
    });

    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener('click', () => {
      sendMessage();
    });
  }

  // Quick Prompt cards
  const promptCards = document.querySelectorAll('.prompt-card');
  promptCards.forEach((card) => {
    card.addEventListener('click', () => {
      const promptText = card.dataset.prompt;
      if (promptText && chatInput) {
        chatInput.value = promptText;
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
        sendMessage();
      }
    });
  });

  // Check URL parameters for CRM prefill or redirection
  const urlParams = new URLSearchParams(window.location.search);
  const prefillQuery = urlParams.get('prefill') || urlParams.get('q');
  const shouldAutoSend = urlParams.get('autosend') === '1' || urlParams.get('autosend') === 'true';

  if (prefillQuery && chatInput) {
    chatInput.value = decodeURIComponent(prefillQuery);
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
    if (sendBtn) sendBtn.disabled = false;

    if (shouldAutoSend) {
      setTimeout(() => {
        sendMessage();
      }, 250);
    } else {
      chatInput.focus();
    }
  }

  // New Chat Button
  const btnNewChat = document.getElementById('btnNewChat');
  if (btnNewChat) {
    btnNewChat.addEventListener('click', async () => {
      try {
        const resp = await fetch('/api/chat/new/', { credentials: 'same-origin' });
        const data = await resp.json();
        if (data.session_id) {
          window.location.href = `/?session_id=${data.session_id}`;
        }
      } catch (err) {
        window.location.href = '/';
      }
    });
  }

  // Source Preview Links
  document.addEventListener('click', async (e) => {
    const citationPill = e.target.closest('.citation-pill');
    if (citationPill && citationPill.dataset.title && sourceModal) {
      e.preventDefault();
      const chunkId = citationPill.dataset.chunkId;
      const documentId = citationPill.dataset.documentId;
      const title = citationPill.dataset.title || 'Document';
      const page = citationPill.dataset.page || '1';
      const score = citationPill.dataset.score || '';

      document.getElementById('modalDocTitle').textContent = `${title} (Page ${page})`;
      document.getElementById('modalScoreBadge').textContent = score ? `Relevance: ${Math.round(score * 100)}%` : '';
      const bodyEl = document.getElementById('modalChunkBody');
      if (modalViewDocumentLink) {
        if (documentId) {
          modalViewDocumentLink.href = `/api/document/${encodeURIComponent(documentId)}/view/`;
          modalViewDocumentLink.style.display = 'inline-flex';
        } else {
          modalViewDocumentLink.removeAttribute('href');
          modalViewDocumentLink.style.display = 'none';
        }
      }
      bodyEl.innerHTML = '<p style="color:var(--text-muted)">Loading document snippet...</p>';
      sourceModal.showModal();

      if (chunkId) {
        try {
          const resp = await fetch(`/api/chunk/${encodeURIComponent(chunkId)}/`);
          if (resp.ok) {
            const data = await resp.json();
            if (modalViewDocumentLink && data.document_id) {
              modalViewDocumentLink.href = `/api/document/${encodeURIComponent(data.document_id)}/view/`;
              modalViewDocumentLink.style.display = 'inline-flex';
            }
            bodyEl.innerHTML = `<div style="white-space: pre-wrap; font-size:0.9rem; line-height:1.6;">${escapeHtml(data.content)}</div>`;
            return;
          }
        } catch (err) {
          console.error(err);
        }
      }
      // Fallback to embedded snippet
      const snippet = citationPill.dataset.snippet || 'Snippet not available';
      bodyEl.innerHTML = `<div style="white-space: pre-wrap; font-size:0.9rem; line-height:1.6;">${escapeHtml(snippet)}</div>`;
    }

    // Feedback Thumbs Up / Down
    const feedbackBtn = e.target.closest('.btn-feedback');
    if (feedbackBtn) {
      const messageId = feedbackBtn.dataset.messageId;
      const rating = parseInt(feedbackBtn.dataset.rating, 10);
      submitFeedback(messageId, rating, feedbackBtn);
    }

    // Delete Session Button
    const delBtn = e.target.closest('.history-del-btn');
    if (delBtn) {
      e.preventDefault();
      e.stopPropagation();
      const sid = delBtn.dataset.sessionId;
      if (confirm('Delete this conversation history?')) {
        try {
          await fetch(`/api/chat/session/${sid}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() }
          });
          const historyRow = delBtn.closest('.history-item');
          if (historyRow) historyRow.remove();
          if (activeSessionInput && activeSessionInput.value === sid) {
            window.location.href = '/';
          }
        } catch (err) {
          console.error(err);
        }
      }
    }
  });

  // Send Message Function
  async function sendMessage() {
    if (!chatInput) return;
    const text = chatInput.value.trim();
    if (!text) return;

    // Hide welcome screen
    if (welcomeScreen) {
      welcomeScreen.style.display = 'none';
    }

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    if (sendBtn) sendBtn.disabled = true;

    // Append User Message to UI
    appendMessage('user', text);
    scrollToBottom();

    // Append Assistant Message placeholder with typing animation
    const assistantRow = createAssistantMessageElement();
    chatMessagesList.appendChild(assistantRow);
    scrollToBottom();

    const textBubble = assistantRow.querySelector('.message-bubble');
    const actionsWrap = assistantRow.querySelector('.message-actions');
    const citationsWrap = assistantRow.querySelector('.citations-wrap');
    const citationsList = assistantRow.querySelector('.citations-list');

    let accumulatedText = "";
    const sessionId = activeSessionInput ? activeSessionInput.value : "";

    try {
      const response = await fetch('/api/chat/stream/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // keep remainder

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const payload = JSON.parse(line.substring(6));
              if (payload.token) {
                accumulatedText += payload.token;
                textBubble.innerHTML = formatMarkdown(accumulatedText);
                scrollToBottom();
              } else if (payload.done) {
                if (payload.session_id && activeSessionInput && !activeSessionInput.value) {
                  activeSessionInput.value = payload.session_id;
                  // Update URL state without page reload
                  window.history.replaceState({}, '', `/?session_id=${payload.session_id}`);
                }

                // Render sources citations
                if (payload.sources && payload.sources.length > 0) {
                  citationsWrap.style.display = 'flex';
                  citationsList.innerHTML = '';
                  payload.sources.forEach(src => {
                    const pill = document.createElement('a');
                    pill.className = 'citation-pill';
                    pill.href = '#';
                    pill.dataset.chunkId = src.chunk_id || '';
                    pill.dataset.documentId = src.document_id || '';
                    pill.dataset.title = src.title;
                    pill.dataset.page = src.page_number;
                    pill.dataset.score = src.score;
                    pill.dataset.snippet = src.snippet;
                    pill.innerHTML = `📎 ${escapeHtml(src.title)} <span class="citation-badge">p.${src.page_number}</span>`;
                    citationsList.appendChild(pill);
                  });
                }

                // Show latency and feedback actions
                actionsWrap.style.display = 'flex';
                if (payload.latency_ms) {
                  const latTag = actionsWrap.querySelector('.latency-tag');
                  if (latTag) latTag.textContent = `${(payload.latency_ms / 1000).toFixed(2)}s`;
                }

                if (payload.message_id) {
                  const thumbsUp = actionsWrap.querySelector('.btn-feedback[data-rating="1"]');
                  const thumbsDown = actionsWrap.querySelector('.btn-feedback[data-rating="-1"]');
                  if (thumbsUp) thumbsUp.dataset.messageId = payload.message_id;
                  if (thumbsDown) thumbsDown.dataset.messageId = payload.message_id;
                }
              }
            } catch (jsonErr) {
              console.error("JSON parse error on stream", jsonErr);
            }
          }
        }
      }
    } catch (err) {
      console.error('Streaming error:', err);
      textBubble.innerHTML = `<p style="color:var(--accent-rose)">⚠️ An error occurred while communicating with the knowledge assistant. Please try again.</p>`;
    } finally {
      if (sendBtn) sendBtn.disabled = false;
      scrollToBottom();
    }
  }

  function appendMessage(sender, text) {
    const row = document.createElement('div');
    row.className = `message-row ${sender}`;
    row.innerHTML = `
      <div class="message-bubble-wrap">
        <div class="message-bubble">${escapeHtml(text)}</div>
      </div>
      <div class="message-avatar ${sender}">
        ${sender === 'user' ? '👤' : '🤖'}
      </div>
    `;
    chatMessagesList.appendChild(row);
  }

  function createAssistantMessageElement() {
    const row = document.createElement('div');
    row.className = 'message-row assistant';
    row.innerHTML = `
      <div class="message-avatar ai">🤖</div>
      <div class="message-bubble-wrap">
        <div class="message-bubble">
          <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
          </div>
        </div>
        <div class="citations-wrap" style="display: none;">
          <div class="citations-header">
            <span>Verified Sources</span>
          </div>
          <div class="citations-list"></div>
        </div>
        <div class="message-actions" style="display: none;">
          <button class="action-btn btn-feedback" data-rating="1" title="Helpful answer">👍 Helpful</button>
          <button class="action-btn btn-feedback" data-rating="-1" title="Unhelpful or inaccurate">👎 Report issue</button>
          <span class="latency-tag"></span>
        </div>
      </div>
    `;
    return row;
  }

  async function submitFeedback(messageId, rating, btnElement) {
    if (!messageId) return;
    try {
      const resp = await fetch('/api/feedback/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          message_id: messageId,
          rating: rating
        })
      });
      if (resp.ok) {
        const parent = btnElement.parentElement;
        const allBtns = parent.querySelectorAll('.btn-feedback');
        allBtns.forEach(b => {
          b.classList.remove('active-thumbs-up', 'active-thumbs-down');
        });
        if (rating === 1) {
          btnElement.classList.add('active-thumbs-up');
        } else {
          btnElement.classList.add('active-thumbs-down');
        }
      }
    } catch (err) {
      console.error(err);
    }
  }

  function scrollToBottom() {
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
      c = c.trim();
      if (c.startsWith('miiciq_csrftoken=')) {
        return c.substring('miiciq_csrftoken='.length);
      }
      if (c.startsWith('csrftoken=')) {
        return c.substring(10);
      }
    }
    const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
    return tokenInput ? tokenInput.value : '';
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatMarkdown(text) {
    if (!text) return '';
    // Basic Markdown Parser (headers, bold, bullet points, numbers, inline code)
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Inline code
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');
    // Bullet points
    const lines = html.split('\n');
    let formattedLines = [];
    let inList = false;

    for (let line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('• ') || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList) {
          formattedLines.push('<ul>');
          inList = true;
        }
        formattedLines.push(`<li>${trimmed.substring(2)}</li>`);
      } else {
        if (inList) {
          formattedLines.push('</ul>');
          inList = false;
        }
        if (trimmed) {
          formattedLines.push(`<p>${line}</p>`);
        }
      }
    }
    if (inList) {
      formattedLines.push('</ul>');
    }
    return formattedLines.join('');
  }
});
