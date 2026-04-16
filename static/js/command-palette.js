/* =========================================================================
   COMMAND PALETTE — Cmd/Ctrl+K
   ========================================================================= */

(function() {
    const commands = [
        // Navigation
        { label: 'Go to Query', desc: 'Natural language database queries', action: () => location.href = '/', section: 'Navigate' },
        { label: 'Go to Overview', desc: 'Database structure & stats', action: () => location.href = '/overview', section: 'Navigate' },
        { label: 'Go to Analysis', desc: 'AI-powered data analysis', action: () => location.href = '/analysis', section: 'Navigate' },
        { label: 'Go to Dashboards', desc: 'Chart & table collections', action: () => location.href = '/dashboards', section: 'Navigate' },
        { label: 'Go to Databases', desc: 'Manage connections', action: () => location.href = '/databases', section: 'Navigate' },
        { label: 'Go to Create Database', desc: 'Create a new database', action: () => location.href = '/create-database', section: 'Navigate' },
        { label: 'Go to Snapshots', desc: 'Backup & restore', action: () => location.href = '/snapshots', section: 'Navigate' },
        { label: 'Go to Command Guide', desc: 'Command reference & intent analyzer', action: () => location.href = '/command-guide', section: 'Navigate' },
        { label: 'Go to Admin', desc: 'LLM metrics & configuration', action: () => location.href = '/admin', section: 'Navigate' },
        // Quick commands
        { label: 'Show Tables', desc: 'List all tables in the database', action: () => runQuickCommand('show tables'), section: 'Commands' },
        { label: 'Show Foreign Keys', desc: 'See all table relationships', action: () => runQuickCommand('show foreign keys'), section: 'Commands' },
        { label: 'Show Indexes', desc: 'List all indexes', action: () => runQuickCommand('show indexes'), section: 'Commands' },
        { label: 'Show Table Counts', desc: 'Row counts for each table', action: () => runQuickCommand('show table counts'), section: 'Commands' },
        { label: 'Show Constraints', desc: 'PKs, FKs, unique, not null', action: () => runQuickCommand('show constraints'), section: 'Commands' },
        // Actions
        { label: 'Export as CSV', desc: 'Download last query results', action: () => location.href = '/export', section: 'Actions' },
        { label: 'Export as PowerPoint', desc: 'Download presentation', action: () => location.href = '/export/ppt', section: 'Actions' },
        { label: 'Create Snapshot', desc: 'Backup current database', action: () => { const f = document.createElement('form'); f.method='POST'; f.action='/snapshots/create'; document.body.appendChild(f); f.submit(); }, section: 'Actions' },
        { label: 'Logout', desc: 'Sign out of Meridian', action: () => location.href = '/logout', section: 'Actions' },
    ];

    function runQuickCommand(cmd) {
        const form = document.createElement('form');
        form.method = 'POST'; form.action = '/';
        const input = document.createElement('input');
        input.type = 'hidden'; input.name = 'command'; input.value = cmd;
        form.appendChild(input); document.body.appendChild(form); form.submit();
    }

    // Create palette DOM
    const overlay = document.createElement('div');
    overlay.id = 'cmd-palette';
    overlay.innerHTML = `
        <div class="cmd-palette-backdrop"></div>
        <div class="cmd-palette-box">
            <div class="cmd-palette-input-wrap">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--text-dim); flex-shrink:0;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input type="text" id="cmd-palette-input" placeholder="Type a command..." autocomplete="off" spellcheck="false">
                <kbd class="cmd-palette-esc">ESC</kbd>
            </div>
            <div id="cmd-palette-list" class="cmd-palette-list"></div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Style
    const style = document.createElement('style');
    style.textContent = `
        #cmd-palette { display:none; position:fixed; inset:0; z-index:9999; }
        #cmd-palette.open { display:block; }
        .cmd-palette-backdrop { position:absolute; inset:0; background:rgba(0,0,0,0.6); backdrop-filter:blur(4px); }
        .cmd-palette-box { position:relative; max-width:560px; margin:min(20vh, 120px) auto 0; background:var(--bg-subtle); border:1px solid var(--border); border-radius:var(--r-lg); box-shadow:0 24px 80px rgba(0,0,0,0.5); overflow:hidden; animation:cmdFadeIn 0.15s ease; }
        @keyframes cmdFadeIn { from { opacity:0; transform:scale(0.97) translateY(-8px); } to { opacity:1; transform:scale(1) translateY(0); } }
        .cmd-palette-input-wrap { display:flex; align-items:center; gap:10px; padding:14px 16px; border-bottom:1px solid var(--border); }
        #cmd-palette-input { flex:1; background:transparent; border:none; color:var(--text); font-size:0.95rem; outline:none; padding:0; }
        #cmd-palette-input::placeholder { color:var(--text-dim); }
        #cmd-palette-input:focus { box-shadow:none; }
        .cmd-palette-esc { font-size:0.6rem; padding:2px 6px; border-radius:4px; background:var(--surface); border:1px solid var(--border); color:var(--text-dim); font-family:inherit; }
        .cmd-palette-list { max-height:360px; overflow-y:auto; padding:6px; scrollbar-width:thin; scrollbar-color:var(--surface-2) transparent; }
        .cmd-palette-section { font-size:0.6rem; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:var(--text-dim); padding:10px 10px 4px; }
        .cmd-palette-item { display:flex; align-items:center; gap:12px; padding:10px 12px; border-radius:var(--r-sm); cursor:pointer; transition:background 0.1s; }
        .cmd-palette-item:hover, .cmd-palette-item.active { background:var(--surface-2); }
        .cmd-palette-item .cmd-label { font-size:0.85rem; font-weight:500; color:var(--text); }
        .cmd-palette-item .cmd-desc { font-size:0.72rem; color:var(--text-dim); margin-left:auto; white-space:nowrap; }
        .cmd-palette-empty { padding:24px; text-align:center; color:var(--text-dim); font-size:0.85rem; }
    `;
    document.head.appendChild(style);

    const input = document.getElementById('cmd-palette-input');
    const list = document.getElementById('cmd-palette-list');
    let activeIndex = 0;
    let filtered = [];

    function open() {
        overlay.classList.add('open');
        input.value = '';
        activeIndex = 0;
        render('');
        requestAnimationFrame(() => input.focus());
    }

    function close() {
        overlay.classList.remove('open');
    }

    function render(query) {
        const q = query.toLowerCase();
        filtered = q ? commands.filter(c =>
            c.label.toLowerCase().includes(q) ||
            c.desc.toLowerCase().includes(q) ||
            c.section.toLowerCase().includes(q)
        ) : commands;

        if (filtered.length === 0) {
            list.innerHTML = '<div class="cmd-palette-empty">No results found</div>';
            return;
        }

        let html = '';
        let lastSection = '';
        filtered.forEach((cmd, i) => {
            if (cmd.section !== lastSection) {
                lastSection = cmd.section;
                html += `<div class="cmd-palette-section">${cmd.section}</div>`;
            }
            html += `<div class="cmd-palette-item ${i === activeIndex ? 'active' : ''}" data-index="${i}">
                <span class="cmd-label">${cmd.label}</span>
                <span class="cmd-desc">${cmd.desc}</span>
            </div>`;
        });
        list.innerHTML = html;

        // Click handlers
        list.querySelectorAll('.cmd-palette-item').forEach(el => {
            el.addEventListener('click', () => {
                const idx = parseInt(el.dataset.index);
                close();
                filtered[idx].action();
            });
        });
    }

    function updateActive() {
        list.querySelectorAll('.cmd-palette-item').forEach((el, i) => {
            el.classList.toggle('active', i === activeIndex);
        });
        // Scroll active into view
        const activeEl = list.querySelector('.cmd-palette-item.active');
        if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
    }

    input.addEventListener('input', () => {
        activeIndex = 0;
        render(input.value);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, filtered.length - 1);
            updateActive();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            updateActive();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (filtered[activeIndex]) {
                close();
                filtered[activeIndex].action();
            }
        } else if (e.key === 'Escape') {
            close();
        }
    });

    // Close on backdrop click
    overlay.querySelector('.cmd-palette-backdrop').addEventListener('click', close);

    // Global shortcut: Cmd/Ctrl+K
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            if (overlay.classList.contains('open')) close();
            else open();
        }
    });

    // Expose globally
    window.CommandPalette = { open, close };
})();
