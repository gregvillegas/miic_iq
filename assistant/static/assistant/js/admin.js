/**
 * MIICiQ — Admin & Analytics Dashboard Client Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // Tab switching
  const tabButtons = document.querySelectorAll('.admin-tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.dataset.tab;
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.style.display = 'none');

      btn.classList.add('active');
      const targetPane = document.getElementById(targetTab);
      if (targetPane) targetPane.style.display = 'block';
    });
  });

  // Rebuild Index button
  const btnRebuild = document.getElementById('btnRebuildIndex');
  if (btnRebuild) {
    btnRebuild.addEventListener('click', async () => {
      if (!confirm('Rebuild the entire vector store and BM25 index from all documents? This may take several seconds.')) {
        return;
      }
      btnRebuild.disabled = true;
      btnRebuild.textContent = '🔄 Rebuilding Index...';
      try {
        const resp = await fetch('/api/admin/rebuild-index/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() }
        });
        const data = await resp.json();
        if (data.status === 'success') {
          alert(`Index rebuild complete!\nIndexed: ${data.stats.successful} documents (${data.stats.total_chunks} chunks) in ${data.stats.duration_seconds}s.`);
          window.location.reload();
        } else {
          alert('Failed to rebuild index.');
        }
      } catch (err) {
        alert('Error rebuilding index: ' + err.message);
      } finally {
        btnRebuild.disabled = false;
        btnRebuild.textContent = '🔄 Rebuild Vector Index';
      }
    });
  }

  // Document Upload Form
  const uploadForm = document.getElementById('docUploadForm');
  const uploadBtn = document.getElementById('btnUploadSubmit');
  const uploadStatus = document.getElementById('uploadStatus');

  if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(uploadForm);
      if (!formData.get('file')) {
        alert('Please select a file to upload.');
        return;
      }

      uploadBtn.disabled = true;
      uploadBtn.textContent = 'Uploading & Ingesting...';
      if (uploadStatus) uploadStatus.textContent = 'Parsing text and creating vector embeddings...';

      try {
        const resp = await fetch('/api/admin/upload/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
          body: formData
        });
        const data = await resp.json();
        if (data.status === 'success') {
          if (uploadStatus) uploadStatus.innerHTML = `<span style="color:var(--accent-emerald)">✅ ${data.message} (${data.chunks} chunks generated)</span>`;
          setTimeout(() => { window.location.reload(); }, 1200);
        } else {
          if (uploadStatus) uploadStatus.innerHTML = `<span style="color:var(--accent-rose)">❌ ${data.error || data.message}</span>`;
        }
      } catch (err) {
        if (uploadStatus) uploadStatus.innerHTML = `<span style="color:var(--accent-rose)">❌ Error: ${err.message}</span>`;
      } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload & Ingest';
      }
    });
  }

  // Re-index Single Document
  document.addEventListener('click', async (e) => {
    const reindexBtn = e.target.closest('.btn-reindex-doc');
    if (reindexBtn) {
      const docId = reindexBtn.dataset.docId;
      reindexBtn.disabled = true;
      reindexBtn.textContent = 'Indexing...';
      try {
        const resp = await fetch(`/api/admin/reindex/${docId}/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() }
        });
        const data = await resp.json();
        alert(data.message);
        window.location.reload();
      } catch (err) {
        alert('Error reindexing: ' + err.message);
        reindexBtn.disabled = false;
        reindexBtn.textContent = 'Re-index';
      }
    }

    // Delete Single Document
    const deleteBtn = e.target.closest('.btn-delete-doc');
    if (deleteBtn) {
      const docId = deleteBtn.dataset.docId;
      const title = deleteBtn.dataset.docTitle || 'this document';
      if (confirm(`Are you sure you want to delete "${title}"? This will purge its vector chunks.`)) {
        try {
          const resp = await fetch(`/api/admin/delete/${docId}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() }
          });
          const row = deleteBtn.closest('tr');
          if (row) row.remove();
        } catch (err) {
          alert('Delete failed: ' + err.message);
        }
      }
    }
  });

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
});
