/* =========================================================================
   TOAST NOTIFICATION SYSTEM
   ========================================================================= */

(function() {
    // Create container
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed; bottom:20px; right:20px; z-index:10000; display:flex; flex-direction:column-reverse; gap:8px; pointer-events:none;';
    document.body.appendChild(container);

    const style = document.createElement('style');
    style.textContent = `
        .toast {
            pointer-events:auto;
            min-width:280px;
            max-width:420px;
            padding:12px 16px;
            border-radius:var(--r-md, 12px);
            font-size:0.85rem;
            font-family:inherit;
            display:flex;
            align-items:center;
            gap:10px;
            animation:toastIn 0.3s ease;
            position:relative;
            overflow:hidden;
            box-shadow:0 8px 32px rgba(0,0,0,0.3);
        }
        .toast.removing { animation:toastOut 0.25s ease forwards; }
        .toast-success { background:#0d2818; border:1px solid rgba(34,197,94,0.3); color:#86efac; }
        .toast-error { background:#2d0a0a; border:1px solid rgba(239,68,68,0.3); color:#fca5a5; }
        .toast-warning { background:#2d1f05; border:1px solid rgba(245,158,11,0.3); color:#fcd34d; }
        .toast-info { background:#0a1a2d; border:1px solid rgba(59,130,246,0.3); color:#93c5fd; }
        .toast-msg { flex:1; line-height:1.4; }
        .toast-close { background:none; border:none; color:inherit; cursor:pointer; opacity:0.5; padding:4px; font-size:1rem; line-height:1; }
        .toast-close:hover { opacity:1; }
        .toast-progress { position:absolute; bottom:0; left:0; height:2px; border-radius:0 0 0 12px; transition:width linear; }
        .toast-success .toast-progress { background:rgba(34,197,94,0.5); }
        .toast-error .toast-progress { background:rgba(239,68,68,0.5); }
        .toast-warning .toast-progress { background:rgba(245,158,11,0.5); }
        .toast-info .toast-progress { background:rgba(59,130,246,0.5); }
        @keyframes toastIn { from { opacity:0; transform:translateY(16px) scale(0.95); } to { opacity:1; transform:translateY(0) scale(1); } }
        @keyframes toastOut { from { opacity:1; transform:translateY(0); } to { opacity:0; transform:translateY(16px); } }
    `;
    document.head.appendChild(style);

    function show(message, type, duration) {
        duration = duration || 4000;
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-msg">${message}</span>
            <button class="toast-close" onclick="this.parentElement.classList.add('removing'); setTimeout(() => this.parentElement.remove(), 250);">&times;</button>
            <div class="toast-progress" style="width:100%;"></div>
        `;
        container.appendChild(toast);

        // Animate progress bar
        const progress = toast.querySelector('.toast-progress');
        requestAnimationFrame(() => {
            progress.style.transitionDuration = duration + 'ms';
            progress.style.width = '0%';
        });

        // Auto-remove
        setTimeout(() => {
            toast.classList.add('removing');
            setTimeout(() => toast.remove(), 250);
        }, duration);
    }

    window.Toast = {
        success: (msg, dur) => show(msg, 'success', dur),
        error: (msg, dur) => show(msg, 'error', dur),
        warning: (msg, dur) => show(msg, 'warning', dur),
        info: (msg, dur) => show(msg, 'info', dur),
    };
})();
