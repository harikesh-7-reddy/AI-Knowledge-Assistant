import React, { useEffect, useMemo, useRef, useState } from 'react';

const api = async (path, options = {}, token = '') => {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, { ...options, headers });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail || 'Something went wrong. Please try again.');
  return data;
};

const initials = (name = '') => name.split(/\s+/).filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase() || 'U';
const formatDate = value => value ? new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
const formatBytes = bytes => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('enterprise_brain_token') || '');
  const [user, setUser] = useState(null);
  const [page, setPage] = useState('chat');
  const [stats, setStats] = useState({ documents: 0, chunks: 0, questions: 0, users: 0 });
  const [documents, setDocuments] = useState([]);
  const [history, setHistory] = useState([]);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [userForm, setUserForm] = useState({ email: '', full_name: '', password: '', role: 'employee', department: 'General' });
  const [loginForm, setLoginForm] = useState({ email: 'admin@example.com', password: 'AdminDemo123!' });
  const chatEndRef = useRef(null);

  const isAdmin = user?.role === 'admin';

  const loadWorkspace = async activeToken => {
    const [me, statData, docs, recent] = await Promise.all([
      api('/api/auth/me', {}, activeToken),
      api('/api/dashboard/stats', {}, activeToken),
      api('/api/documents', {}, activeToken),
      api('/api/chat/history', {}, activeToken),
    ]);
    setUser(me); setStats(statData); setDocuments(docs); setHistory(recent);
  };

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    loadWorkspace(token).catch(() => {
      sessionStorage.removeItem('enterprise_brain_token'); setToken(''); setUser(null);
    }).finally(() => setLoading(false));
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(''), 3200);
    return () => clearTimeout(id);
  }, [toast]);

  const login = async event => {
    event.preventDefault(); setError(''); setLoading(true);
    try {
      const result = await api('/api/auth/login', { method: 'POST', body: JSON.stringify(loginForm) });
      sessionStorage.setItem('enterprise_brain_token', result.access_token);
      setToken(result.access_token); setUser(result.user);
      await loadWorkspace(result.access_token);
      setMessages([]); setPage('chat');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const logout = () => {
    sessionStorage.removeItem('enterprise_brain_token'); setToken(''); setUser(null); setMessages([]); setPage('chat');
  };

  const refreshWorkspace = async () => {
    const [statData, docs] = await Promise.all([
      api('/api/dashboard/stats', {}, token), api('/api/documents', {}, token),
    ]);
    setStats(statData); setDocuments(docs);
  };

  const ask = async (text = question) => {
    const clean = text.trim(); if (!clean || busy) return;
    setQuestion(''); setError('');
    const userMessage = { id: crypto.randomUUID(), role: 'user', content: clean };
    setMessages(prev => [...prev, userMessage]); setBusy(true);
    try {
      const result = await api('/api/chat', { method: 'POST', body: JSON.stringify({ question: clean }) }, token);
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: result.answer, citations: result.citations, mode: result.mode, evidenceFound: result.evidence_found }]);
      setStats(prev => ({ ...prev, questions: prev.questions + 1 }));
      api('/api/chat/history', {}, token).then(setHistory).catch(() => {});
    } catch (err) {
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `I couldn't complete that request: ${err.message}`, citations: [], error: true }]);
    } finally { setBusy(false); }
  };

  const refreshAdmin = async () => {
    const [u, a] = await Promise.all([api('/api/admin/users', {}, token), api('/api/admin/audit', {}, token)]);
    setUsers(u); setAudit(a);
  };

  useEffect(() => {
    if (page === 'admin' && isAdmin) refreshAdmin().catch(err => setToast(err.message));
  }, [page, isAdmin]);

  const upload = async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const file = form.elements.file.files[0];
    if (!file) { setToast('Choose a file to upload.'); return; }
    const body = new FormData();
    body.append('file', file); body.append('title', form.elements.title.value);
    body.append('access_level', form.elements.access_level.value); body.append('department', form.elements.department.value);
    setUploading(true);
    try {
      const result = await api('/api/documents', { method: 'POST', body }, token);
      await refreshWorkspace(); setUploadOpen(false); form.reset();
      setToast(`${result.title} indexed successfully (${result.chunk_count} passages).`);
    } catch (err) { setToast(err.message); }
    finally { setUploading(false); }
  };

  const deleteDocument = async doc => {
    if (!window.confirm(`Delete “${doc.title}”? This also removes its indexed passages.`)) return;
    try { await api(`/api/documents/${doc.id}`, { method: 'DELETE' }, token); await refreshWorkspace(); setToast('Document deleted.'); }
    catch (err) { setToast(err.message); }
  };

  const reindexDocuments = async () => {
    if (!window.confirm('Rebuild Gemini embeddings for all existing passages? Documents, users, access permissions, chats and audit history will be preserved.')) return;
    setReindexing(true);
    try {
      const result = await api('/api/admin/reindex', { method: 'POST' }, token);
      setToast(`Gemini reindexed ${result.chunks} passages across ${result.documents} documents.`);
      await refreshWorkspace();
      await refreshAdmin();
    } catch (err) { setToast(err.message); }
    finally { setReindexing(false); }
  };

  const createUser = async event => {
    event.preventDefault();
    try {
      await api('/api/admin/users', { method: 'POST', body: JSON.stringify(userForm) }, token);
      setUserForm({ email: '', full_name: '', password: '', role: 'employee', department: 'General' });
      await refreshAdmin(); await refreshWorkspace(); setToast('Account created successfully.');
    } catch (err) { setToast(err.message); }
  };

  const download = async doc => {
    try {
      const response = await fetch(`/api/documents/${doc.id}/download`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || 'Download failed'); }
      const blob = await response.blob(); const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = doc.original_filename; anchor.click(); URL.revokeObjectURL(url);
    } catch (err) { setToast(err.message); }
  };

  const departmentDocs = useMemo(() => documents.filter(d => d.access_level === 'department').length, [documents]);

  if (loading) return <div className="boot-screen"><div className="brand-mark large">EB</div><p>Opening your knowledge workspace…</p></div>;

  if (!token || !user) return <LoginScreen form={loginForm} setForm={setLoginForm} onSubmit={login} error={error} loading={loading} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><div className="brand-mark">EB</div><div><div className="brand-name">Enterprise Brain</div><div className="brand-sub">KNOWLEDGE WORKSPACE</div></div></div>
        <div className="workspace-pill"><span className="pulse-dot" /> Private workspace</div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav">
          <button className={page === 'chat' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('chat')}><span className="nav-icon">✳</span> Ask knowledge</button>
          <button className={page === 'documents' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('documents')}><span className="nav-icon">▤</span> Documents <span className="nav-count">{stats.documents}</span></button>
          {isAdmin && <><div className="nav-label admin-label">ADMINISTRATION</div><button className={page === 'admin' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('admin')}><span className="nav-icon">⚙</span> Admin console</button></>}
          {history.length > 0 && <><div className="nav-label recent-label">RECENT QUESTIONS</div>{history.slice(0, 4).map(item => <button key={item.id} className="history-nav-item" title={item.question} onClick={() => { setPage('chat'); ask(item.question); }}><span>↳</span>{item.question}</button>)}</>}
        </nav>
        <div className="sidebar-bottom">
          <div className="security-note"><span>⌑</span><div><strong>Access controlled</strong><small>Answers use documents you can view.</small></div></div>
          <button type="button" className="sidebar-signout" onClick={logout} title="Sign out of Enterprise Brain">
            <span aria-hidden="true">↪</span> Sign out
          </button>
          <div className="profile-row"><div className="avatar">{initials(user.full_name)}</div><div className="profile-info"><strong>{user.full_name}</strong><span>{user.department} · {user.role}</span></div><button type="button" className="icon-button logout-button" title="Sign out" aria-label="Sign out" onClick={logout}>↗</button></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar"><div><div className="eyebrow">{page === 'chat' ? 'INTELLIGENCE' : page === 'documents' ? 'KNOWLEDGE BASE' : 'CONTROL CENTER'}</div><h1>{page === 'chat' ? 'Ask your company knowledge' : page === 'documents' ? 'Document library' : 'Administration'}</h1></div><div className="topbar-actions"><span className="connection-status"><span className="green-dot" /> Connected</span><button type="button" className="topbar-signout" onClick={logout} title="Sign out of Enterprise Brain"><span aria-hidden="true">↪</span><span>Sign out</span></button><div className="topbar-avatar" aria-label={`Signed in as ${user.full_name}`} title={user.full_name}>{initials(user.full_name)}</div></div></header>

        {page === 'chat' && <section className="chat-page">
          {messages.length === 0 ? <div className="welcome-panel">
            <div className="welcome-orbit"><span>✳</span></div>
            <div className="eyebrow centered">YOUR COMPANY, UNDERSTOOD</div>
            <h2>Good to see you, {user.full_name.split(' ')[0]}.</h2>
            <p className="welcome-copy">Ask a question across the documents available to you. Every answer is grounded in source passages you can verify.</p>
            <div className="suggestion-grid">
              {[
                ['▧', 'What is the annual leave policy?', 'What is the annual leave policy?'],
                ['⌘', 'How do I get IT support?', 'How do I get IT support?'],
                ['↗', 'What is the release process?', 'What is the engineering release process?'],
              ].map(([icon, label, value]) => <button key={label} className="suggestion-card" onClick={() => ask(value)}><span>{icon}</span><strong>{label}</strong><i>↗</i></button>)}
            </div>
            <div className="permission-hint"><span>◈</span> Results are automatically filtered by your {user.department} access.</div>
          </div> : <div className="conversation">
            <div className="conversation-intro"><span className="conversation-date">CURRENT SESSION</span><span className="conversation-count">{messages.filter(m => m.role === 'user').length} questions</span></div>
            {messages.map(message => <Message key={message.id} message={message} token={token} />)}
            {busy && <div className="message assistant-message"><div className="assistant-avatar">✳</div><div className="message-body"><div className="message-author">Enterprise Brain <span>Searching accessible sources…</span></div><div className="typing"><i/><i/><i/></div></div></div>}
            <div ref={chatEndRef} />
          </div>}
          <div className="composer-wrap"><form className="composer" onSubmit={e => { e.preventDefault(); ask(); }}><div className="composer-top"><textarea value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } }} placeholder="Ask anything about your company documents…" rows="1" maxLength="2000"/><button className="send-button" type="submit" disabled={!question.trim() || busy}>↑</button></div><div className="composer-footer"><span><span className="mini-lock">⌑</span> Answers are grounded in documents you can access</span><span>ENTER TO SEND · SHIFT + ENTER FOR NEW LINE</span></div></form><div className="disclaimer">Enterprise Brain can make mistakes. Verify important details against the cited source documents.</div></div>
        </section>}

        {page === 'documents' && <section className="content-page">
          <div className="metrics-row"><Metric label="Accessible documents" value={stats.documents} icon="▤"/><Metric label="Indexed passages" value={stats.chunks} icon="⌗"/><Metric label="Restricted to your department" value={departmentDocs} icon="◈"/></div>
          <div className="section-heading"><div><h2>Your document library</h2><p>Only documents permitted for your account appear here.</p></div>{isAdmin && <button className="primary-button" onClick={() => setUploadOpen(true)}>＋ Upload document</button>}</div>
          {documents.length ? <div className="document-table-wrap"><table className="data-table"><thead><tr><th>DOCUMENT</th><th>ACCESS</th><th>SIZE</th><th>INDEXED</th><th></th></tr></thead><tbody>{documents.map(doc => <tr key={doc.id}><td><div className="doc-cell"><div className={`file-icon ${doc.extension === '.pdf' ? 'pdf' : doc.extension === '.docx' ? 'word' : 'text'}`}>{doc.extension === '.pdf' ? 'PDF' : doc.extension === '.docx' ? 'DOC' : 'TXT'}</div><div><strong>{doc.title}</strong><span>{doc.original_filename} · {doc.chunk_count} passages</span></div></div></td><td><AccessTag level={doc.access_level} department={doc.department}/></td><td className="muted-cell">{formatBytes(doc.file_size)}</td><td className="muted-cell">{formatDate(doc.created_at)}</td><td><div className="row-actions"><button className="text-action" onClick={() => download(doc)}>↓ Download</button>{isAdmin && <button className="delete-action" onClick={() => deleteDocument(doc)}>Delete</button>}</div></td></tr>)}</tbody></table></div> : <EmptyState title="No documents available" detail="Ask your administrator to add documents to the knowledge base."/>}
          <div className="library-footnote"><span>⌑</span> Access is enforced by the server for search and file downloads—not just hidden in this interface.</div>
        </section>}

        {page === 'admin' && isAdmin && <section className="content-page admin-page">
          <div className="metrics-row"><Metric label="Active users" value={stats.users} icon="♙"/><Metric label="Knowledge documents" value={stats.documents} icon="▤"/><Metric label="Indexed passages" value={stats.chunks} icon="⌗"/></div>
          <div className="panel reindex-panel">
            <div className="panel-heading"><div><h2>Gemini search index</h2><p>Rebuild vectors for existing passages after switching to Gemini. Existing documents and access rules are not changed.</p></div><button className="primary-button" type="button" onClick={reindexDocuments} disabled={reindexing}>{reindexing ? 'Reindexing…' : 'Rebuild embeddings →'}</button></div>
            <div className="role-explainer"><strong>Safe in-place update</strong><span>Only the stored passage vectors are replaced. Document records, user accounts, roles, permissions, question history and audit records remain intact.</span></div>
          </div>
          <div className="admin-grid">
            <div className="panel user-create-panel"><div className="panel-heading"><div><h2>Create an account</h2><p>Assign a department to scope document access.</p></div><span className="panel-icon">♙</span></div>
              <form className="stack-form" onSubmit={createUser}>
                <label>Full name<input required minLength="2" value={userForm.full_name} onChange={e => setUserForm({ ...userForm, full_name: e.target.value })} placeholder="Alex Morgan"/></label>
                <label>Work email<input type="email" required value={userForm.email} onChange={e => setUserForm({ ...userForm, email: e.target.value })} placeholder="alex@company.com"/></label>
                <div className="form-two"><label>Role<select value={userForm.role} onChange={e => setUserForm({ ...userForm, role: e.target.value })}><option value="employee">Employee</option><option value="admin">Administrator</option></select></label><label>Department<select value={userForm.department} onChange={e => setUserForm({ ...userForm, department: e.target.value })}>{['General','HR','Engineering','Finance','Sales','Operations','IT'].map(x => <option key={x}>{x}</option>)}</select></label></div>
                <label>Temporary password<input type="password" required minLength="8" value={userForm.password} onChange={e => setUserForm({ ...userForm, password: e.target.value })} placeholder="At least 8 characters"/></label>
                <button className="primary-button full-button" type="submit">Create account <span>→</span></button>
              </form>
              <div className="role-explainer"><strong>Permission model</strong><span>Public: all users · Department: matching department · Private: owner and administrators</span></div>
            </div>
            <div className="panel users-panel"><div className="panel-heading"><div><h2>Workspace members</h2><p>{users.length} registered accounts</p></div><span className="panel-icon">♧</span></div>
              <div className="members-list">{users.map(member => <div className="member-row" key={member.id}><div className="avatar small-avatar">{initials(member.full_name)}</div><div className="member-info"><strong>{member.full_name}</strong><span>{member.email}</span></div><div className="member-meta"><span className={`role-pill ${member.role}`}>{member.role}</span><small>{member.department}</small></div></div>)}</div>
            </div>
          </div>
          <div className="panel audit-panel"><div className="panel-heading"><div><h2>Recent audit activity</h2><p>Sign-ins, document operations and knowledge queries.</p></div><span className="panel-icon">◷</span></div>
            {audit.length ? <div className="audit-list">{audit.slice(0, 8).map(item => <div className="audit-row" key={item.id}><span className="audit-dot"/><div><strong>{item.action.replaceAll('_', ' ')}</strong><span>{item.detail}</span></div><div className="audit-meta">{item.full_name}<small>{formatDate(item.created_at)}</small></div></div>)}</div> : <p className="empty-inline">No audit events yet.</p>}
          </div>
        </section>}
        <footer className="app-footer"><span>ENTERPRISE BRAIN <b>·</b> SECURE KNOWLEDGE ASSISTANT</span><span>Evidence-led answers · Permission-aware retrieval</span></footer>
      </main>

      {uploadOpen && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setUploadOpen(false); }}><div className="modal"><div className="modal-heading"><div><span className="eyebrow">KNOWLEDGE INGESTION</span><h2>Add a document</h2><p>Text is extracted, split into passages and indexed for search.</p></div><button className="icon-button" onClick={() => setUploadOpen(false)}>×</button></div><form className="stack-form" onSubmit={upload}><label>Document title<input name="title" placeholder="e.g. Employee Leave Policy"/></label><label className="file-drop"><input name="file" type="file" accept=".pdf,.docx,.txt,.md" required/><span className="upload-cloud">↑</span><strong>Choose a document</strong><small>PDF, DOCX, TXT or Markdown · Max 20 MB</small></label><div className="form-two"><label>Who can access it?<select name="access_level" defaultValue="public"><option value="public">All employees (public)</option><option value="department">One department</option><option value="private">Uploader + administrators (private)</option></select></label><label>Department<input name="department" defaultValue="General" placeholder="e.g. HR"/></label></div><div className="modal-note"><span>⌑</span> Permission checks happen during retrieval, before document passages reach the AI model.</div><div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setUploadOpen(false)}>Cancel</button><button className="primary-button" type="submit" disabled={uploading}>{uploading ? 'Processing…' : 'Upload and index →'}</button></div></form></div></div>}
      {toast && <div className="toast"><span>✓</span>{toast}</div>}
    </div>
  );
}

function LoginScreen({ form, setForm, onSubmit, error, loading }) {
  return <div className="login-screen"><div className="login-visual"><div className="login-visual-inner"><div className="brand-lockup"><div className="brand-mark">EB</div><div><div className="brand-name">Enterprise Brain</div><div className="brand-sub">KNOWLEDGE WORKSPACE</div></div></div><div className="login-art"><div className="art-ring ring-one"/><div className="art-ring ring-two"/><div className="art-core">✳</div><span className="art-node node-one">▤</span><span className="art-node node-two">⌘</span><span className="art-node node-three">◈</span><span className="art-node node-four">✦</span></div><div className="login-tagline"><span className="eyebrow">THE KNOWLEDGE LAYER FOR WORK</span><h1>Every answer.<br/><em>Backed by evidence.</em></h1><p>One trusted place to search company knowledge—with citations, context and access controls built in.</p></div><div className="visual-footer"><span>PRIVATE BY DESIGN</span><span>RAG · SOURCE CITATIONS · ACCESS CONTROL</span></div></div></div><div className="login-form-side"><div className="login-form-wrap"><div className="mobile-brand"><div className="brand-mark">EB</div><strong>Enterprise Brain</strong></div><span className="eyebrow">WELCOME BACK</span><h2>Sign in to your workspace</h2><p className="login-subtitle">Use your company account to access the knowledge base.</p><form className="stack-form login-form" onSubmit={onSubmit}><label>Work email<input type="email" autoComplete="username" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}/></label><label>Password<input type="password" autoComplete="current-password" required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}/></label>{error && <div className="error-banner">{error}</div>}<button className="primary-button full-button" disabled={loading}>{loading ? 'Signing in…' : 'Sign in securely'} <span>→</span></button></form><div className="demo-credentials"><div className="demo-heading"><span>DEMO ACCESS</span><span className="demo-badge">READY TO EXPLORE</span></div><div className="credential-row"><span>Administrator</span><button onClick={() => setForm({ email: 'admin@example.com', password: 'AdminDemo123!' })}>Use demo account ↗</button></div><div className="credential-row"><span>HR · Engineering · Employee</span><small>Demo users listed in README</small></div></div><div className="login-security"><span>⌑</span> Secure session · Role-based access</div></div></div></div>;
}

function Message({ message, token }) {
  const isUser = message.role === 'user';
  return <div className={`message ${isUser ? 'user-message' : 'assistant-message'}`}><div className={isUser ? 'user-avatar' : 'assistant-avatar'}>{isUser ? 'You' : '✳'}</div><div className="message-body"><div className="message-author">{isUser ? 'You' : 'Enterprise Brain'}{!isUser && message.mode && <span className="mode-label">{message.mode === 'ai_generated' ? 'AI RESPONSE' : message.mode === 'no_evidence' ? 'NO EVIDENCE' : 'LOCAL EVIDENCE'}</span>}</div><div className="message-text">{message.content.split('\n').map((line, i) => <React.Fragment key={i}>{line || <br/>}{i < message.content.split('\n').length - 1 && <br/>}</React.Fragment>)}</div>{!isUser && message.citations?.length > 0 && <div className="citations-block"><div className="citations-heading"><span>▤</span> Supporting passages <small>{message.citations.length} sources</small></div><div className="citation-grid">{message.citations.map(source => <div className="citation-card" key={source.source_id}><div className="citation-top"><span className="source-id">{source.source_id}</span><button onClick={async () => { try { const response = await fetch(`/api/documents/${source.document_id}/download`, { headers: { Authorization: `Bearer ${token}` } }); if (!response.ok) throw new Error('Source is no longer available'); const blob = await response.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = source.filename; a.click(); URL.revokeObjectURL(url); } catch { /* The citation passage remains available for verification. */ } }} title="Download source document">↗</button></div><strong>{source.title}</strong><span className="citation-page">{source.page_number ? `Page ${source.page_number}` : 'Page not available'} · {Math.round(source.relevance * 100)}% match</span><p>“{source.passage}”</p></div>)}</div></div>}{!isUser && !message.error && <div className="answer-footnote"><span>⌑</span> Only passages available to your account were searched.</div>}</div></div>;
}

function Metric({ label, value, icon }) { return <div className="metric-card"><div className="metric-icon">{icon}</div><div><strong>{value}</strong><span>{label}</span></div></div>; }
function AccessTag({ level, department }) { return <span className={`access-tag ${level}`}><i/>{level === 'public' ? 'Public' : level === 'department' ? department : 'Private'}</span>; }
function EmptyState({ title, detail }) { return <div className="empty-state"><div className="empty-icon">▤</div><h3>{title}</h3><p>{detail}</p></div>; }

export default App;
