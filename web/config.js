const languageConfig = {
    // ...existing language configurations...
};

function saveConfig(config) {
    // ...existing saveConfig implementation...
}

function setupLanguageSearch() {
    const searchInput = document.querySelector('#language-search');
    const dropdown = document.createElement('div');
    dropdown.className = 'language-dropdown';
    searchInput.parentNode.appendChild(dropdown);

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const languages = Object.keys(languageConfig);
        
        dropdown.innerHTML = languages
            .filter(lang => lang.toLowerCase().includes(query))
            .map(lang => `
                <div class="language-item" data-lang="${lang}">
                    <img class="language-flag" src="web/flags/${languageConfig[lang].flag}" alt="${lang} flag">
                    <span>${lang}</span>
                </div>
            `).join('');
        
        dropdown.classList.add('show');
    });

    dropdown.addEventListener('click', (e) => {
        const langItem = e.target.closest('.language-item');
        if (langItem) {
            const lang = langItem.dataset.lang;
            addSelectedLanguage(lang);
            dropdown.classList.remove('show');
            searchInput.value = '';
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.language-search-container')) {
            dropdown.classList.remove('show');
        }
    });
}

function addSelectedLanguage(lang) {
    const container = document.querySelector('#selected-languages');
    const span = document.createElement('span');
    span.className = 'selected-language';
    span.innerHTML = `
        <img class="language-flag" src="web/flags/${languageConfig[lang].flag}" alt="${lang} flag">
        ${lang}
        <span class="remove-language">×</span>
    `;
    
    span.querySelector('.remove-language').addEventListener('click', () => {
        span.remove();
        updateLanguageConfig();
    });
    
    container.appendChild(span);
    updateLanguageConfig();
}

function updateLanguageConfig() {
    const selectedLangs = Array.from(document.querySelectorAll('.selected-language'))
        .map(el => el.textContent.trim().slice(0, -1));
    saveConfig({ languages: selectedLangs });
}

function setupAboutTab() {
    const aboutContent = `
        <div class="about-container">
            <div class="about-header">
                <h2>About Ankipedia</h2>
                <p>Ankipedia is developed by William Guy to help medical students create high-quality Anki cards from Wikipedia articles.</p>
            </div>
            <div class="about-links">
                <p><strong>GitHub Repository:</strong> <a href="https://github.com/yourusername/ankipedia" target="_blank">github.com/yourusername/ankipedia</a></p>
            </div>
            <div class="support-section">
                <p>If you find this addon helpful, consider supporting development:</p>
                <a href="https://www.buymeacoffee.com/williamguy" target="_blank" class="bmc-button">
                    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee">
                </a>
            </div>
            <div class="about-credits">
                <p>Special thanks to:</p>
                <ul>
                    <li>Flag icons provided by GoSquared</li>
                    <li>Content sourced from Wikipedia</li>
                </ul>
            </div>
        </div>
    `;
    
    document.querySelector('#about-tab').innerHTML = aboutContent;
}

// Initialize the new features
document.addEventListener('DOMContentLoaded', () => {
    // ...existing code...
    setupLanguageSearch();
    setupAboutTab();
});