/**
 * ==============================================================================
 * MIICiQ — Embeddable CRM Chatbot Widget
 * Drop this script into any Django CRM template to provide an AI copilot that
 * redirects to the MIIC_iQ knowledge assistant with prefilled queries.
 * ==============================================================================
 */

(function () {
  'use strict';

  // Prevent multiple initializations
  if (window.__MIICIQ_WIDGET_LOADED__) return;
  window.__MIICIQ_WIDGET_LOADED__ = true;

  // Retrieve configuration from current script tag or global object
  const currentScript = document.currentScript || document.querySelector('script[src*="miiciq-widget.js"]');
  const globalConfig = window.MIICIQ_CONFIG || {};

  const config = {
    appUrl: (currentScript && currentScript.dataset.miiciqUrl) || globalConfig.appUrl || window.location.origin,
    mode: (currentScript && currentScript.dataset.mode) || globalConfig.mode || 'redirect', // 'redirect', 'new_tab', or 'slideout'
    position: (currentScript && currentScript.dataset.position) || globalConfig.position || 'bottom-right',
    buttonText: (currentScript && currentScript.dataset.buttonText) || globalConfig.buttonText || 'Ask MIICiQ',
    title: (currentScript && currentScript.dataset.title) || globalConfig.title || 'MIICiQ Sales & Policy Assistant',
    subtitle: (currentScript && currentScript.dataset.subtitle) || globalConfig.subtitle || 'Private AI Knowledge Assistant',
  };

  // Ensure trailing slash is stripped from appUrl
  config.appUrl = config.appUrl.replace(/\/+$/, '');

  // 1. Inject Stylesheet if not already linked
  const cssHref = `${config.appUrl}/static/assistant/css/miiciq-widget.css`;
  if (!document.querySelector(`link[href*="miiciq-widget.css"]`)) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = cssHref;
    document.head.appendChild(link);
  }

  // 2. Build DOM Elements
  const root = document.createElement('div');
  root.className = `miiciq-widget-root ${config.position === 'bottom-left' ? 'pos-bottom-left' : ''}`;
  root.id = 'miiciqWidgetRoot';

  root.innerHTML = `
    <!-- Floating Trigger Button -->
    <button type="button" class="miiciq-trigger-btn" id="miiciqTriggerBtn" aria-expanded="false" aria-label="Open MIICiQ knowledge assistant">
      <div class="miiciq-trigger-icon">🤖</div>
      <span class="miiciq-pulse-indicator" title="Local RAG Online"></span>
      <span>${escapeHtml(config.buttonText)}</span>
    </button>

    <!-- Popup Chat Window -->
    <div class="miiciq-chat-window" id="miiciqChatWindow" role="dialog" aria-labelledby="miiciqHeaderTitle">
      <div class="miiciq-header">
        <div class="miiciq-header-title-wrap">
          <div class="miiciq-header-logo">IQ</div>
          <div class="miiciq-header-text">
            <h3 id="miiciqHeaderTitle">${escapeHtml(config.title)}</h3>
            <p>${escapeHtml(config.subtitle)}</p>
          </div>
        </div>
        <div class="miiciq-header-controls">
          <button type="button" class="miiciq-control-btn" id="miiciqBtnExpand" title="Open full MIICiQ application in new tab">↗</button>
          <button type="button" class="miiciq-control-btn" id="miiciqBtnClose" title="Close widget">✕</button>
        </div>
      </div>

      <div class="miiciq-body">
        <div class="miiciq-intro-banner">
          <span>💡</span>
          <div>
            <strong>Need instant sales order or policy help?</strong>
            <p style="margin:2px 0 0; color:#cbd5e1;">Ask below to be redirected directly into MIICiQ with verified citations.</p>
          </div>
        </div>

        <div>
          <div class="miiciq-quick-title">Quick CRM Inquiries:</div>
          <div class="miiciq-prompts-list">
            <button type="button" class="miiciq-prompt-item" data-query="How do I process a Sales Order in ERP? What are the step-by-step procedures?">
              <span>📦 Sales Order (SO-101) Workflow</span>
              <span class="miiciq-prompt-arrow">→</span>
            </button>
            <button type="button" class="miiciq-prompt-item" data-query="What are the discount approval thresholds and required signoffs?">
              <span>💰 Discount Approval Matrix</span>
              <span class="miiciq-prompt-arrow">→</span>
            </button>
            <button type="button" class="miiciq-prompt-item" data-query="What are the payment terms and customer credit check rules?">
              <span>📑 Payment Terms & Credit Limits</span>
              <span class="miiciq-prompt-arrow">→</span>
            </button>
            <button type="button" class="miiciq-prompt-item" data-query="What are the travel and meal per diem limits?">
              <span>✈️ Travel & Expense Policy</span>
              <span class="miiciq-prompt-arrow">→</span>
            </button>
          </div>
        </div>

        <div class="miiciq-redirect-card">
          <p>Looking for full chat history or semantic search?</p>
          <a href="${config.appUrl}/" class="miiciq-btn-launch" id="miiciqBtnOpenApp" ${config.mode === 'new_tab' ? 'target="_blank"' : ''}>
            Launch Full MIICiQ Assistant ↗
          </a>
        </div>
      </div>

      <div class="miiciq-footer">
        <form id="miiciqWidgetForm">
          <div class="miiciq-input-wrap">
            <input type="text" id="miiciqWidgetInput" class="miiciq-input-field" placeholder="Ask about SO process, policies, discounts..." autocomplete="off">
            <button type="submit" class="miiciq-btn-send" title="Ask in MIICiQ">➤</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Optional Slideout Drawer for In-Page Iframe Mode -->
    <div class="miiciq-slideout-drawer" id="miiciqSlideoutDrawer">
      <div class="miiciq-drawer-header">
        <strong style="font-size:14px; color:#ffffff;">MIICiQ Knowledge Assistant</strong>
        <div style="display:flex; gap:8px;">
          <a href="${config.appUrl}/" target="_blank" class="miiciq-control-btn" title="Open in new window">↗</a>
          <button type="button" class="miiciq-control-btn" id="miiciqCloseDrawer">✕</button>
        </div>
      </div>
      <iframe src="about:blank" id="miiciqDrawerIframe" class="miiciq-drawer-iframe" title="MIICiQ Application"></iframe>
    </div>
  `;

  document.body.appendChild(root);

  // 3. Cache Elements
  const triggerBtn = document.getElementById('miiciqTriggerBtn');
  const chatWindow = document.getElementById('miiciqChatWindow');
  const btnClose = document.getElementById('miiciqBtnClose');
  const btnExpand = document.getElementById('miiciqBtnExpand');
  const widgetForm = document.getElementById('miiciqWidgetForm');
  const widgetInput = document.getElementById('miiciqWidgetInput');
  const slideoutDrawer = document.getElementById('miiciqSlideoutDrawer');
  const drawerIframe = document.getElementById('miiciqDrawerIframe');
  const closeDrawerBtn = document.getElementById('miiciqCloseDrawer');

  // Toggle Chat Window
  function toggleWindow(open) {
    const isOpen = open !== undefined ? open : !chatWindow.classList.contains('open');
    chatWindow.classList.toggle('open', isOpen);
    triggerBtn.setAttribute('aria-expanded', isOpen);
    if (isOpen) {
      setTimeout(() => widgetInput && widgetInput.focus(), 100);
    }
  }

  triggerBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleWindow();
  });

  btnClose.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleWindow(false);
  });

  btnExpand.addEventListener('click', (e) => {
    e.stopPropagation();
    handleRedirect('');
  });

  // Light-dismiss click outside popup
  document.addEventListener('click', (e) => {
    if (chatWindow.classList.contains('open') && !root.contains(e.target)) {
      toggleWindow(false);
    }
  });

  // Handle Query Submission & Redirection
  function handleRedirect(queryText) {
    const trimmed = (queryText || '').trim();
    let targetUrl = `${config.appUrl}/`;
    if (trimmed) {
      targetUrl = `${config.appUrl}/?prefill=${encodeURIComponent(trimmed)}&autosend=1`;
    }

    if (config.mode === 'slideout') {
      // In-page slideout drawer
      toggleWindow(false);
      drawerIframe.src = targetUrl;
      slideoutDrawer.classList.add('open');
    } else if (config.mode === 'new_tab') {
      window.open(targetUrl, '_blank');
      toggleWindow(false);
    } else {
      // Default: Direct redirection to MIIC_iQ
      window.location.href = targetUrl;
    }
  }

  // Handle Form Submit
  if (widgetForm) {
    widgetForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const query = widgetInput.value;
      if (query && query.trim()) {
        handleRedirect(query);
      } else {
        handleRedirect('');
      }
    });
  }

  // Handle Quick Prompts click
  const promptButtons = root.querySelectorAll('.miiciq-prompt-item');
  promptButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.query;
      handleRedirect(q);
    });
  });

  // Drawer Close
  if (closeDrawerBtn && slideoutDrawer) {
    closeDrawerBtn.addEventListener('click', () => {
      slideoutDrawer.classList.remove('open');
      drawerIframe.src = 'about:blank';
    });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  // Expose global controller
  window.MIICiQ = {
    open: () => toggleWindow(true),
    close: () => toggleWindow(false),
    ask: (q) => handleRedirect(q),
  };
})();
