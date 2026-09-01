// ...existing code...

function renderThemeOptions() {
    // ...existing code...
    const themeOptions = [
        {
            name: "Light",
            icon: "Light.svg",
            value: "light",
            disabled: false,
            note: ""
        },
        {
            name: "Dark",
            icon: "Dark.svg",
            value: "dark",
            disabled: false,
            note: ""
        },
        {
            name: "Auto",
            icon: "Auto.svg",
            value: "auto",
            disabled: true,
            note: "Coming soon."
        }
    ];

    const container = document.getElementById("theme-switcher-options");
    container.innerHTML = "";
    themeOptions.forEach(option => {
        const btn = document.createElement("button");
        btn.className = "theme-option";
        btn.disabled = option.disabled;
        btn.style.opacity = option.disabled ? "0.5" : "1";
        btn.innerHTML = `
            <img src="static/${option.icon}" alt="${option.name} theme" />
            <span>${option.name}</span>
            ${option.note ? `<div class="theme-note">${option.note}</div>` : ""}
        `;
        btn.onclick = () => {
            if (!option.disabled) setTheme(option.value);
        };
        container.appendChild(btn);
    });
}

// ...existing code...