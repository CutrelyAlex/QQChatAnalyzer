/*
 * Theme Toggle (cyberpunk <-> readable)
 * - Default: cyberpunk (no attribute)
 * - Readable: html[data-theme="readable"]
 */

(function () {
    const STORAGE_KEY = 'qq-chat-theme';
    const THEMES = {
        CYBER: 'cyber',
        READABLE: 'readable'
    };

    function getCurrentTheme() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved === THEMES.READABLE) return THEMES.READABLE;
        return THEMES.CYBER;
    }

    function applyTheme(theme) {
        const html = document.documentElement;
        if (theme === THEMES.READABLE) {
            html.setAttribute('data-theme', 'readable');
        } else {
            html.removeAttribute('data-theme');
        }

        const btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            if (theme === THEMES.READABLE) {
                btn.textContent = '赛博风格';
                btn.title = '切换回赛博朋克风格';
            } else {
                btn.textContent = '易读风格';
                btn.title = '切换为更易阅读的风格';
            }
        }
    }

    function toggleTheme() {
        const current = getCurrentTheme();
        const next = current === THEMES.READABLE ? THEMES.CYBER : THEMES.READABLE;
        localStorage.setItem(STORAGE_KEY, next);
        applyTheme(next);
    }

    function init() {
        applyTheme(getCurrentTheme());

        const btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            btn.addEventListener('click', toggleTheme);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
