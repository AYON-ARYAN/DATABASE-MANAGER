/* =========================================================================
   TABLE SORT — Client-side column sorting
   ========================================================================= */

(function() {
    document.addEventListener('click', function(e) {
        const th = e.target.closest('th[data-sortable]');
        if (!th) return;

        const table = th.closest('table');
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const colIndex = Array.from(th.parentElement.children).indexOf(th);
        const rows = Array.from(tbody.querySelectorAll('tr'));

        // Determine sort direction
        const currentDir = th.dataset.sortDir || 'none';
        const newDir = currentDir === 'asc' ? 'desc' : 'asc';

        // Reset all headers
        th.parentElement.querySelectorAll('th').forEach(h => {
            h.dataset.sortDir = 'none';
            h.style.cursor = 'pointer';
            // Remove sort indicator
            const indicator = h.querySelector('.sort-indicator');
            if (indicator) indicator.textContent = '';
        });

        th.dataset.sortDir = newDir;

        // Add sort indicator
        let indicator = th.querySelector('.sort-indicator');
        if (!indicator) {
            indicator = document.createElement('span');
            indicator.className = 'sort-indicator';
            indicator.style.cssText = 'margin-left:4px; font-size:0.6rem; opacity:0.6;';
            th.appendChild(indicator);
        }
        indicator.textContent = newDir === 'asc' ? ' \u25B2' : ' \u25BC';

        // Sort rows
        rows.sort((a, b) => {
            const aVal = a.children[colIndex]?.textContent.trim() || '';
            const bVal = b.children[colIndex]?.textContent.trim() || '';

            // Try numeric comparison
            const aNum = parseFloat(aVal.replace(/,/g, ''));
            const bNum = parseFloat(bVal.replace(/,/g, ''));

            if (!isNaN(aNum) && !isNaN(bNum)) {
                return newDir === 'asc' ? aNum - bNum : bNum - aNum;
            }

            // String comparison
            return newDir === 'asc'
                ? aVal.localeCompare(bVal)
                : bVal.localeCompare(aVal);
        });

        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
    });

    // Make all result table headers sortable
    function initSortableHeaders() {
        document.querySelectorAll('.table-wrapper table th, .widget-table th').forEach(th => {
            if (!th.hasAttribute('data-sortable')) {
                th.setAttribute('data-sortable', '');
                th.style.cursor = 'pointer';
                th.title = 'Click to sort';
            }
        });
    }

    // Init on load and observe for dynamic content
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSortableHeaders);
    } else {
        initSortableHeaders();
    }

    // Re-init when new tables appear (for AJAX content)
    const observer = new MutationObserver(initSortableHeaders);
    observer.observe(document.body, { childList: true, subtree: true });
})();
