// ...existing code...

function isDarkTheme() {
    // Adjust this logic to match your theme detection
    return document.body.classList.contains('dark');
}

function showContextMenu(x, y) {
    // ...existing code to create/show context menu...
    const menu = document.getElementById('context-menu');
    // ...existing code...
    if (isDarkTheme()) {
        menu.classList.add('dark');
    } else {
        menu.classList.remove('dark');
    }
    // ...existing code...
}

// ...existing code...