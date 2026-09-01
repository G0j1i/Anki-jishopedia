from aqt import mw
from aqt import gui_hooks
from aqt.reviewer import Reviewer
from aqt.qt import QAction, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from aqt.webview import AnkiWebView
from .jisho_bridge import JishoBridge
import os
import json
import colorsys
import requests

# Allow Anki to serve our web assets from /_addons/
mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js)")

# Load config.json for this addon
config = mw.addonManager.getConfig(__name__)
if config is None:
    print("Ankipedia: config.json not found or invalid.")
else:
    print("Ankipedia config loaded.")

def darken_hex_color(hex_color, delta):
    """Darken a hex color by delta (negative for darker, positive for lighter)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c*2 for c in hex_color])
    r, g, b = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
    l = max(0, min(1, l + delta))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255))

def on_webview_will_set_content(web_content, context):
    # Only modify the reviewer content
    if not isinstance(context, Reviewer):
        return
    # Get the addon's internal package name
    pkg = mw.addonManager.addonFromModule(__name__)

    # Inject CSS and JS files in correct order
    web_content.css.append(f"/_addons/{pkg}/web/web.css")
    web_content.js.append(f"/_addons/{pkg}/web/web.js")    # web.js comes after

    # Inject the selected Wikipedia language and class name as JS variables
    config = mw.addonManager.getConfig(__name__)
    if config is None:
        lang = "en"
        class_name = "ankipedia"
        theme = "auto"
        border_style = "solid"
        border_thickness = 1
        border_color = "#0db5be"
        cursor_style = "pointer"
        tooltip_btn_bg = "#0db5be"
        tooltip_btn_fg = "#fff"
    else:
        lang = config.get("wikipedia_lang", "en")
        class_name = config.get("class_name", "ankipedia")
        theme = config.get("theme", "auto")
        border_style = config.get("border_style", "solid")
        border_thickness = config.get("border_thickness", 1)
        border_color = config.get("border_color", "#0db5be")
        cursor_style = "pointer"  # Always pointer, ignore config
        tooltip_btn_bg = config.get("tooltip_btn_bg", "#0db5be")
        tooltip_btn_fg = config.get("tooltip_btn_fg", "#fff")

    # Calculate hover/active colors for tooltip button
    tooltip_btn_bg_hover = darken_hex_color(tooltip_btn_bg, -0.08)
    tooltip_btn_bg_active = darken_hex_color(tooltip_btn_bg, -0.16)

    # --- Fix: Set data-ankipedia-theme attribute on <html> for system theme support ---
    # This ensures CSS selectors like [data-ankipedia-theme="auto"] work with system theme
    web_content.head += (
        f'<script>'
        f'window.ANKIPEDIA_WIKI_LANG = "{lang}";'
        f'window.ANKIPEDIA_CLASS_NAME = "{class_name}";'
        f'window.ANKIPEDIA_THEME = "{theme}";'
        f'window.ANKIPEDIA_BLOCKED_WORDS = {json.dumps(config.get("blocked_words", []))};'
        f'window.ANKIPEDIA_BLOCKED_UNIGRAMS = {json.dumps(config.get("blocked_unigrams", []))};'
        f'window.ANKIPEDIA_BORDER_STYLE = "{border_style}";'
        f'window.ANKIPEDIA_BORDER_THICKNESS = {border_thickness};'
        f'window.ANKIPEDIA_BORDER_COLOR = "{border_color}";'
        f'window.ANKIPEDIA_CURSOR_STYLE = "{cursor_style}";'
        f'window.ANKIPEDIA_TOOLTIP_BTN_BG = "{tooltip_btn_bg}";'
        f'window.ANKIPEDIA_TOOLTIP_BTN_FG = "{tooltip_btn_fg}";'
        # Set data-ankipedia-theme="auto" and data-ankipedia-theme-system="dark"/"light" for auto mode
        f'''
        (function() {{
            function setThemeAttr() {{
                var theme = "{theme}";
                var html = document.documentElement;
                if (theme === "auto") {{
                    html.setAttribute("data-ankipedia-theme", "auto");
                    var isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
                    html.setAttribute("data-ankipedia-theme-system", isDark ? "dark" : "light");
                }} else {{
                    html.setAttribute("data-ankipedia-theme", theme);
                    html.removeAttribute("data-ankipedia-theme-system");
                }}
            }}
            setThemeAttr();
            if ("{theme}" === "auto") {{
                window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", setThemeAttr);
            }}
        }})();
        '''
        f'</script>'
    )
    
    web_content.head += (
        f'''
        <script>
            window.ANKIPEDIA_CLASS_NAME = "{class_name}";
            window.ANKIPEDIA_THEME = "{theme}";  // This will be 'auto', 'light', or 'dark'
        </script>
        '''
    )
    
    # Add custom CSS for tippy tooltip theming and context menu
    web_content.head += (
        f'''
        <style>
            /* Base theme styling */
            :root {{
                --ankipedia-tippy-bg: #fff;
                --ankipedia-tippy-color: #333;
                --ankipedia-tippy-border: #ddd;
                --ankipedia-tippy-shadow: rgba(0, 0, 0, 0.1);
                --ankipedia-context-bg: #fff;
                --ankipedia-context-color: #333;
                --ankipedia-context-hover-bg: #f0f0f0;
                --ankipedia-context-hover-color: #111;
                --ankipedia-context-border: #ddd;
                --ankipedia-context-shadow: rgba(0, 0, 0, 0.15);
            }}
            
            /* Dark theme variables */
            html[data-ankipedia-theme="dark"] {{
                --ankipedia-tippy-bg: #333;
                --ankipedia-tippy-color: #eee;
                --ankipedia-tippy-border: #555;
                --ankipedia-tippy-shadow: rgba(0, 0, 0, 0.3);
                --ankipedia-context-bg: #333;
                --ankipedia-context-color: #eee;
                --ankipedia-context-hover-bg: #444;
                --ankipedia-context-hover-color: #fff;
                --ankipedia-context-border: #555;
                --ankipedia-context-shadow: rgba(0, 0, 0, 0.3);
            }}
            
            /* Auto theme based on system preference */
            html[data-ankipedia-theme="auto"][data-ankipedia-theme-system="dark"] {{
                --ankipedia-tippy-bg: #333;
                --ankipedia-tippy-color: #eee;
                --ankipedia-tippy-border: #555;
                --ankipedia-tippy-shadow: rgba(0, 0, 0, 0.3);
                --ankipedia-context-bg: #333;
                --ankipedia-context-color: #eee;
                --ankipedia-context-hover-bg: #444;
                --ankipedia-context-hover-color: #fff;
                --ankipedia-context-border: #555;
                --ankipedia-context-shadow: rgba(0, 0, 0, 0.3);
            }}
            
            /* Tippy tooltip styling */
            .tippy-box[data-theme~='ankipedia'] {{
                background-color: var(--ankipedia-tippy-bg);
                color: var(--ankipedia-tippy-color);
                border: 1px solid var(--ankipedia-tippy-border);
                box-shadow: 0 4px 14px var(--ankipedia-tippy-shadow);
            }}
            
            .tippy-box[data-theme~='ankipedia'] .tippy-content {{
                color: var(--ankipedia-tippy-color);
            }}
            
            .tippy-box[data-theme~='ankipedia'] .tippy-arrow::before {{
                background-color: var(--ankipedia-tippy-bg);
                border-color: var(--ankipedia-tippy-border);
            }}
            
            /* Right-click context menu styling */
            .ankipedia-context-menu {{
                background-color: var(--ankipedia-context-bg) !important;
                color: var(--ankipedia-context-color) !important;
                border: 1px solid var(--ankipedia-context-border) !important;
                box-shadow: 0 4px 14px var(--ankipedia-context-shadow) !important;
            }}
            
            .ankipedia-context-menu .menu-item,
            .ankipedia-context-menu div {{
                color: var(--ankipedia-context-color) !important;
                background-color: var(--ankipedia-context-bg) !important;
            }}
            
            .ankipedia-context-menu .menu-item:hover,
            .ankipedia-context-menu div:hover {{
                background-color: var(--ankipedia-context-hover-bg) !important;
                color: var(--ankipedia-context-hover-color) !important;
            }}
            
            /* Ensure context menu doesn't get overridden by other styles */
            #ankipedia-context-menu,
            .ankipedia-context-menu-item {{
                background-color: var(--ankipedia-context-bg) !important;
                color: var(--ankipedia-context-color) !important;
            }}
        </style>
        '''
    )
    
    # Also inject custom CSS for styling the terms
    web_content.head += (
        f'<style>'
        f'.ankipediaTerm {{'
        f'  border-bottom: {border_thickness}px {border_style} {border_color};'
        f'  cursor: pointer !important;'
        f'  display: inline-block;'
        f'  width: auto;'
        f'}}'
        f'.tooltip-text a {{'
        f'  background-color: {tooltip_btn_bg};'
        f'  color: {tooltip_btn_fg};'
        f'  border-radius: 4px;'
        f'  padding: 2px 8px;'
        f'  text-decoration: none;'
        f'  transition: background 0.15s;'
        f'}}'
        f'.tooltip-text a:hover {{'
        f'  background-color: {tooltip_btn_bg_hover};'
        f'}}'
        f'.tooltip-text a:active {{'
        f'  background-color: {tooltip_btn_bg_active};'
        f'}}'
        f'</style>'
    )

# Hook into the content rendering
gui_hooks.webview_will_set_content.append(on_webview_will_set_content)

def ankipedia_webview_did_receive_js_message(webview, message, context):
    if not isinstance(message, str) or not message.startswith("ankipedia:block:"):
        return (False, None)  # Not handling this message
        
    parts = message.split(":", 3)
    if len(parts) != 4:
        return (False, None)
        
    _, _, typ, word = parts
    word = word.strip().lower()  # Normalize to lowercase
    if not word:
        return (False, None)
        
    word = word.replace("%20", " ")
    
    # Get current config, create new if none exists
    config = mw.addonManager.getConfig(__name__)
    if config is None:
        config = {"blocked_words": [], "blocked_unigrams": []}
    
    if typ == "word":
        blocked = set(config.get("blocked_words", []))
        blocked.add(word)
        config["blocked_words"] = sorted(list(blocked))
    elif typ == "unigram":
        blocked = set(config.get("blocked_unigrams", []))
        blocked.add(word)
        config["blocked_unigrams"] = sorted(list(blocked))
    else:
        return (False, None)
        
    # Write config to disk
    mw.addonManager.writeConfig(__name__, config)
    
    # Update JavaScript variables in the webview (no reload)
    if hasattr(mw, "reviewer") and mw.reviewer and hasattr(mw.reviewer, "web"):
        mw.reviewer.web.eval(f"""
            window.ANKIPEDIA_BLOCKED_WORDS = {json.dumps(config.get("blocked_words", []))};
            window.ANKIPEDIA_BLOCKED_UNIGRAMS = {json.dumps(config.get("blocked_unigrams", []))};
        """)
    
    # Do NOT reload/re-render the webview
    return (True, None)

# Register the JS message handler
def _setup_ankipedia_context_menu():
    try:
        from aqt import gui_hooks
        gui_hooks.webview_did_receive_js_message.append(ankipedia_webview_did_receive_js_message)
    except Exception:
        pass

_setup_ankipedia_context_menu()

# Initialize the Jisho bridge
jisho_bridge = JishoBridge()

def show_config_dialog():
    config = mw.addonManager.getConfig(__name__)
    if config is None:
        config = {}

    WIKI_LANGS = [
        ("en", "English", "🇬🇧"),
        ("ja", "Japanese", "🇯🇵"),
        ("ru", "Russian", "🇷🇺"),
        ("es", "Spanish", "🇪🇸"),
        ("de", "German", "🇩🇪"),
        ("fr", "French", "🇫🇷"),
        ("it", "Italian", "🇮🇹"),
        ("zh", "Chinese", "🇨🇳"),
        ("fa", "Persian", "🇮🇷"),
        ("pt", "Portuguese", "🇵🇹"),
        ("pl", "Polish", "🇵🇱"),
        ("ar", "Arabic", "🇸🇦"),
        ("tr", "Turkish", "🇹🇷"),
        ("id", "Indonesian", "🇮🇩"),
        ("nl", "Dutch", "🇳🇱"),
        ("vi", "Vietnamese", "🇻🇳"),
        ("ko", "Korean", "🇰🇷"),
        ("uk", "Ukrainian", "🇺🇦"),
        ("th", "Thai", "🇹🇭"),
        ("he", "Hebrew", "🇮🇱"),
        ("cs", "Czech", "🇨Z"),
        ("ro", "Romanian", "🇷O"),
        ("hu", "Hungarian", "🇭U"),
        ("sv", "Swedish", "🇸E"),
        ("fi", "Finnish", "🇫I"),
        ("no", "Norwegian", "🇳O"),
        ("el", "Greek", "🇬R"),
        ("ca", "Catalan", "🇪🇸"),
        ("sh", "Serbo-Croatian", "🇷S"),
        ("bg", "Bulgarian", "🇧G"),
        ("ms", "Malay", "🇲Y"),
        ("sk", "Slovak", "🇸K"),
        ("hr", "Croatian", "🇭R"),
        ("da", "Danish", "🇩K"),
        ("lt", "Lithuanian", "🇱T"),
        ("sl", "Slovenian", "🇸I"),
        ("et", "Estonian", "🇪🇪"),
        ("lv", "Latvian", "🇱V"),
        ("eu", "Basque", "🇪🇸"),
        ("gl", "Galician", "🇪🇸"),
        ("is", "Icelandic", "🇮🇸"),
        ("mk", "Macedonian", "🇲K"),
        ("sq", "Albanian", "🇦L"),
        ("hy", "Armenian", "🇦M"),
        ("az", "Azerbaijani", "🇦🇿"),
    ]
    WIKI_LANGS = [WIKI_LANGS[0]] + sorted(WIKI_LANGS[1:], key=lambda x: x[1])

    from aqt.qt import (QComboBox, QLineEdit, QLabel, QDialog, QVBoxLayout, QHBoxLayout, 
                       QPushButton, QWidget, QSizePolicy, Qt, QRadioButton, QButtonGroup, 
                       QScrollArea, QPlainTextEdit, QTabWidget, QStyledItemDelegate, QSlider)
    try:
        from PyQt6.QtCore import Qt as QtCoreQt, QUrl
        from PyQt6.QtGui import QDesktopServices, QPixmap, QColor, QCursor, QIcon, QPainter, QBrush
        from PyQt6.QtWidgets import QColorDialog, QDoubleSpinBox, QGroupBox, QFrame, QListWidget, QListWidgetItem
    except ImportError:
        from aqt.qt import QUrl, QDesktopServices, QPixmap, QColorDialog, QDoubleSpinBox, QGroupBox, QFrame, QListWidget, QListWidgetItem, QIcon
        QtCoreQt = Qt

    FLAG_PATHS = {
        "en": "web/flags/gb.svg",
        "ja": "web/flags/jp.svg",
        "ru": "web/flags/ru.svg",
        "es": "web/flags/es.svg",
        "de": "web/flags/de.svg",
        "fr": "web/flags/fr.svg",
        "it": "web/flags/it.svg",
        "zh": "web/flags/cn.svg",
        "fa": "web/flags/ir.svg",
        "pt": "web/flags/pt.svg",
        "pl": "web/flags/pl.svg",
        "ar": "web/flags/sa.svg",
        "tr": "web/flags/tr.svg",
        "id": "web/flags/id.svg",
        "nl": "web/flags/nl.svg",
        "vi": "web/flags/vn.svg",
        "ko": "web/flags/kr.svg",
        "uk": "web/flags/ua.svg",
        "th": "web/flags/th.svg",
        "he": "web/flags/il.svg",
        "cs": "web/flags/cz.svg",
        "ro": "web/flags/ro.svg",
        "hu": "web/flags/hu.svg",
        "sv": "web/flags/se.svg",
        "fi": "web/flags/fi.svg",
        "no": "web/flags/no.svg",
        "el": "web/flags/gr.svg",
        "ca": "web/flags/es-ct.svg",
        "sh": "web/flags/rs.svg",
        "bg": "web/flags/bg.svg",
        "ms": "web/flags/my.svg",
        "sk": "web/flags/sk.svg",
        "hr": "web/flags/hr.svg",
        "da": "web/flags/dk.svg",
        "lt": "web/flags/lt.svg",
        "sl": "web/flags/si.svg",
        "et": "web/flags/ee.svg",
        "lv": "web/flags/lv.svg",
        "eu": "web/flags/es-pv.svg",
        "gl": "web/flags/es-ga.svg",
        "is": "web/flags/is.svg",
        "mk": "web/flags/mk.svg",
        "sq": "web/flags/al.svg",
        "hy": "web/flags/am.svg",
        "az": "web/flags/az.svg",
    }

    from aqt.qt import QComboBox, QLineEdit, QLabel, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QSizePolicy, Qt, QRadioButton, QButtonGroup, QScrollArea, QPlainTextEdit, QTabWidget, QStyledItemDelegate

    class PrettyLabel(QLabel):
        def __init__(self, text, bold=False, size=10, color="#222", margin=(0, 0, 8, 0)):
            super().__init__(text)
            font = self.font()
            font.setPointSize(size)
            font.setBold(bold)
            self.setFont(font)
            self.setWordWrap(True)  # Enable word wrap
            self.setStyleSheet(f"color: {color}; margin: {margin[0]}px {margin[1]}px {margin[2]}px {margin[3]}px;")

    class PreviewLabel(QLabel):
        def __init__(self, text="Ankipedia", border_style="solid", border_thickness=1, border_color="#0db5be"):
            super().__init__(text)
            # Store style properties as instance variables
            self.border_style = border_style
            self.border_thickness = border_thickness 
            self.border_color = border_color
            self.setStyleSheet(
                f"border-bottom: {border_thickness}px {border_style} {border_color}; "
                f"cursor: pointer;"
                f"display: inline-block; width: auto;"
                f"font-family: 'DM Sans', -apple-system, -system-ui, Arial;"
                f"font-size: 16px;"
                f"font-weight: 400;"
                f"color: #111;"
            )
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def update_style(self, border_style=None, border_thickness=None, border_color=None):
            # Update stored values if new ones provided
            if border_style is not None:
                self.border_style = border_style
            if border_thickness is not None:
                self.border_thickness = border_thickness
            if border_color is not None:
                self.border_color = border_color
                
            self.setStyleSheet(
                f"border-bottom: {self.border_thickness}px {self.border_style} {self.border_color}; "
                f"cursor: pointer;"
                f"display: inline-block; width: auto;"
                f"font-family: 'DM Sans', -apple-system, -system-ui, Arial;"
                f"font-size: 16px;"
                f"font-weight: 400;"
                f"color: #111;"
            )

    class TooltipButtonPreview(QLabel):
        def __init__(self, bg="#0db5be", fg="#fff"):
            super().__init__("Tooltip Button")
            self.setFixedHeight(32)
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setStyleSheet(f"""
                background-color: {bg};
                color: {fg};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 12pt;
            """)

        def update_style(self, bg, fg):
            self.setStyleSheet(f"""
                background-color: {bg};
                color: {fg};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 12pt;
            """)

    class ConfigDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Ankipedia Options")
            self.setFixedSize(600, 700)
            
            # --- Tab Widget: Make each tab 25% width ---
            self.setStyleSheet("""
                QDialog {
                    background: white;
                    border-radius: 0;
                }
                QTabWidget::pane {
                    border: none;
                    background: white;
                }
                QTabWidget::tab-bar {
                    alignment: center;
                }
                QTabBar::tab {
                    background: #f5f5f5;
                    color: #666;
                    padding: 16px 0;
                    font-size: 13px;
                    border: none;
                    margin: 0;
                    width: 150px;  /* 600px / 4 = 150px for 4 tabs */
                    border-radius: 0;
                }
                QTabBar::tab:selected {
                    background: #0db5be;
                    color: white;
                }
                QPushButton {
                    background: #0db5be;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 4px;
                    font-size: 13px;
                    min-width: 100px;
                }
                QPushButton:hover {
                    background: #0ca3ac;
                }
                QPushButton#cancel {
                    background: #f5f5f5;
                    color: #666;
                }
                QPushButton#cancel:hover {
                    background: #eaeaea;
                }
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    padding: 12px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: white;
                }
                QLineEdit:focus, QComboBox:focus {
                    border-color: #0db5be;
                }
                QFrame, QWidget {
                    background: white;
                }
                QRadioButton {
                    font-size: 13px;
                    color: #444;
                    padding: 8px;
                    background: white;
                }
                QPlainTextEdit {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 12px;
                    background: white;
                }
                /* Make help text smaller */
                QLabel {
                    font-size: 11px;
                    color: #666;
                    background: white;
                }
            """)

            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)

            tabs = QTabWidget()
            main_layout.addWidget(tabs)

            # --- Setup Tab ---
            setup_tab = QWidget()
            setup_scroll = QScrollArea()
            setup_scroll.setWidgetResizable(True)
            setup_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            setup_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            setup_container = QWidget()
            setup_layout = QVBoxLayout(setup_container)
            setup_layout.setContentsMargins(24, 24, 24, 24)
            setup_layout.setSpacing(18)

            # --- Language Dropdown (circle flags, styled like native dropdown) ---
            setup_layout.addWidget(PrettyLabel("Wikipedia Language", bold=True, size=10, margin=(0,0,2,0)))
            self.lang_combo = QComboBox()
            self.lang_combo.setMinimumHeight(40)
            self.lang_combo.setMinimumWidth(280)  # Increase minimum width
            self.lang_combo.setStyleSheet("""
                QComboBox {
                    font-size: 14px;
                    padding: 8px 16px;
                    border: 1.5px solid #ddd;
                    border-radius: 8px;
                    background: white;
                    text-align: left;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 20px;
                }
                QComboBox::down-arrow {
                    image: url(web/down-arrow.svg);
                    width: 12px;
                    height: 12px;
                }
                QComboBox QAbstractItemView,
                QComboBox QScrollArea,
                QComboBox QListView,
                QComboBox QWidget { 
                }
                QComboBox::item {
                    padding: 10px 12px;
                    min-height: 24px;
                }
                QComboBox QAbstractItemView {
                    border: 1.5px solid #ddd;
                    border-radius: 8px;
                    background: white;
                    padding: 4px;
                    selection-background-color: #f5f5f5;
                }
                QComboBox QAbstractItemView::item:first-child {
                    border-bottom: 1px solid #eee;
                    margin-bottom: 4px;
                    padding-bottom: 14px;
                }
                QComboBox QAbstractItemView::item:hover {
                    background-color: #f5f5f5;
                    border-radius: 4px;
                }
                /* Item icon styling */
                QComboBox::item:selected {
                    background-color: transparent;
                }
                QComboBox::item:selected:active {
                    background-color: #f5f5f5;
                }
            """)
            setup_layout.addWidget(self.lang_combo, alignment=Qt.AlignmentFlag.AlignLeft)
            setup_layout.addWidget(PrettyLabel(
                "Select the language of Wikipedia you would like tooltips for.\nMulti-language searching is not available.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            # --- Class Name ---
            setup_layout.addWidget(PrettyLabel("Class Name", bold=True, size=10, margin=(0,0,2,0)))
            self.class_edit = QLineEdit()
            self.class_edit.setText(config.get("class_name", "ankipedia"))
            self.class_edit.setMinimumHeight(32)
            self.class_edit.setStyleSheet("""
                QLineEdit { font-size: 11pt; padding: 8px 12px; text-overflow: ellipsis; }
            """)
            setup_layout.addWidget(self.class_edit)
            setup_layout.addWidget(PrettyLabel(
                "Choose the class name where Ankipedia should show tooltips — use card to show them everywhere, or use the default ankipedia class to control exactly where tooltips appear by adding it to specific parts of your card templates.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            setup_layout.addStretch()
            setup_scroll.setWidget(setup_container)
            tabs.addTab(setup_scroll, "Setup")

            # --- Appearance Tab ---
            appearance_tab = QWidget()
            appearance_scroll = QScrollArea()
            appearance_scroll.setWidgetResizable(True)
            appearance_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            appearance_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            appearance_container = QWidget()
            appearance_layout = QVBoxLayout(appearance_container)
            appearance_layout.setContentsMargins(24, 24, 24, 24)
            appearance_layout.setSpacing(18)

            # --- Restore Defaults Button (right-aligned with note on left) ---
            restore_layout = QHBoxLayout()
            
            # Add note on the left side
            restore_note = QLabel("Note: Theme changes may require exiting your current deck or restarting Anki.")
            restore_note.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
            restore_note.setWordWrap(True)
            restore_layout.addWidget(restore_note, 1)  # Give the label stretch factor of 1
            
            # Add spacer to push button to the right
            restore_layout.addStretch(0)
            
            # Add button on the right
            self.restore_btn = QPushButton("Restore Defaults")
            self.restore_btn.setStyleSheet("""
                QPushButton {
                    background: #e53935;
                    color: white;
                    border: none;
                    padding: 12px 32px;
                    border-radius: 6px;
                    font-size: 13px;
                    min-width: 120px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #c62828;
                }
            """)
            restore_layout.addWidget(self.restore_btn, 0)  # No stretch for button
            appearance_layout.addLayout(restore_layout)
            self.restore_btn.clicked.connect(self.restore_defaults)

            appearance_layout.addWidget(PrettyLabel("Theme", bold=True, size=10, margin=(0,0,2,0)))
            theme_layout = QHBoxLayout()
            theme_layout.setSpacing(12)
            self.theme_group = QButtonGroup()
            themes = [
                ("light", "Light"),
                ("dark", "Dark"),
                ("auto", "Auto")
            ]
            
            addon_dir = os.path.dirname(__file__)
            
            for theme_id, label in themes:
                theme_widget = QWidget()
                theme_layout_inner = QVBoxLayout()
                theme_layout_inner.setContentsMargins(0,0,0,0)
                theme_layout_inner.setSpacing(8)
                
                # Create the preview image container
                preview = QLabel()
                preview.setFixedSize(150, 100)
                preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Use Auto.svg for auto theme
                icon_file = f"{theme_id.capitalize()}.svg" if theme_id != "auto" else "Auto.svg"
                icon_path = os.path.join(addon_dir, "web", icon_file)
                
                if os.path.exists(icon_path):
                    pixmap = QPixmap(icon_path)
                    preview.setPixmap(pixmap.scaled(120, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    # Set border styling based on theme
                    if theme_id == "light":
                        preview.setStyleSheet("background: white; border: 1px solid #e0e0e0; border-radius: 8px;")
                    elif theme_id == "dark":
                        preview.setStyleSheet("background: #2c2c2c; border: 1px solid #404040; border-radius: 8px;")
                    else: # auto
                        preview.setStyleSheet("background: linear-gradient(to right, white 50%, #2c2c2c 50%); border: 1px solid #e0e0e0; border-radius: 8px;")
                else:
                    if theme_id == "light":
                        preview.setStyleSheet("background-color: white; border: 1px solid #e0e0e0; border-radius: 8px;")
                    elif theme_id == "dark":
                        preview.setStyleSheet("background-color: #2c2c2c; border: 1px solid #404040; border-radius: 8px;")
                    else: # auto
                        preview.setStyleSheet("background: linear-gradient(to right, white 50%, #2c2c2c 50%); border: 1px solid #e0e0e0; border-radius: 8px;")
                
                radio_container = QWidget()
                radio_layout = QHBoxLayout()
                radio_layout.setContentsMargins(0,0,0,0)
                radio_layout.setSpacing(2)
                radio = QRadioButton(label)
                radio.setProperty("theme_id", theme_id)
                if theme_id == "auto":
                    # Disable auto theme option
                    radio.setEnabled(False)
                    radio.setStyleSheet("color: #aaa;")
                else:
                    if theme_id == config.get("theme", "auto"):
                        radio.setChecked(True)
                self.theme_group.addButton(radio)
                radio_layout.addStretch()
                radio_layout.addWidget(radio)
                radio_layout.addStretch()
                radio_container.setLayout(radio_layout)
                
                theme_layout_inner.addWidget(preview)
                theme_layout_inner.addWidget(radio_container)
                # Change label for auto theme to "Coming soon"
                if theme_id == "auto":
                    coming_soon = QLabel("Coming soon.")
                    coming_soon.setStyleSheet("color: #888; font-size: 11px; margin-top: 2px;")
                    coming_soon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    theme_layout_inner.addWidget(coming_soon)
                theme_widget.setLayout(theme_layout_inner)
                theme_layout.addWidget(theme_widget)
            
            appearance_layout.addLayout(theme_layout)
            appearance_layout.addWidget(PrettyLabel(
                "Select your preferred tooltip theme.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            # Border Style
            appearance_layout.addWidget(PrettyLabel("Term Border Style", bold=True, size=10, margin=(0,0,2,0)))
            border_style_layout = QHBoxLayout()
            border_style_layout.setSpacing(12)
            self.border_style_group = QButtonGroup()
            border_styles = [
                ("solid", "Solid"),
                ("dotted", "Dotted"),
                ("none", "None")
            ]
            for style_id, label in border_styles:
                radio = QRadioButton(label)
                if style_id == config.get("border_style", "solid"):
                    radio.setChecked(True)
                radio.setProperty("style_id", style_id)
                self.border_style_group.addButton(radio)
                border_style_layout.addWidget(radio)
                radio.toggled.connect(self.update_preview)
            border_style_layout.addStretch()
            appearance_layout.addLayout(border_style_layout)
            appearance_layout.addWidget(PrettyLabel(
                "Select the style for the border below each term.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            # Border Thickness
            appearance_layout.addWidget(PrettyLabel("Border Thickness", bold=True, size=10, margin=(0,0,2,0)))
            thickness_layout = QHBoxLayout()
            thickness_layout.setSpacing(8)
            thickness_layout.setContentsMargins(0, 0, 0, 0)
            self.thickness_slider = QSlider(QtCoreQt.Orientation.Horizontal)
            self.thickness_slider.setMinimum(4)
            self.thickness_slider.setMaximum(12)  # 4 = 1px, 12 = 3px
            self.thickness_slider.setValue(int(config.get("border_thickness", 1) * 4))
            self.thickness_slider.setTickInterval(1)
            self.thickness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            self.thickness_slider.setFixedWidth(120)
            # Remove QDoubleSpinBox, use QLabel for value display
            self.thickness_value_label = QLabel(f"{config.get('border_thickness', 1):.2g} px")
            self.thickness_value_label.setFixedWidth(40)
            self.thickness_value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            def update_thickness_label(val):
                px = val / 4
                self.thickness_value_label.setText(f"{px:.2g} px")
                self.update_preview()
            self.thickness_slider.valueChanged.connect(update_thickness_label)
            thickness_layout.addWidget(self.thickness_slider, 0)
            thickness_layout.addWidget(self.thickness_value_label, 0)
            thickness_layout.addStretch(1)
            appearance_layout.addLayout(thickness_layout)
            appearance_layout.addWidget(PrettyLabel(
                "Adjust the thickness of the border (1px to 3px).",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            # Border Color
            appearance_layout.addWidget(PrettyLabel("Border Color", bold=True, size=10, margin=(0,0,2,0)))
            color_layout = QHBoxLayout()
            self.color_sample = QPushButton("")
            self.color_sample.setFixedSize(40, 30)
            self.color_sample.setStyleSheet(
                f"background-color: {config.get('border_color', '#0db5be')}; border: 1px solid #aaa;"
            )
            self.border_color = config.get("border_color", "#0db5be")
            self.color_sample.clicked.connect(self.choose_color)
            self.color_value = QLineEdit()
            self.color_value.setText(self.border_color)
            self.color_value.setFixedWidth(100)
            self.color_value.textChanged.connect(self.update_color_from_text)
            color_layout.addWidget(self.color_sample)
            color_layout.addWidget(self.color_value)
            color_layout.addStretch()
            appearance_layout.addLayout(color_layout)
            appearance_layout.addWidget(PrettyLabel(
                "Choose the color for the term border.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            # --- Term Preview (after border color) ---
            appearance_layout.addWidget(PrettyLabel("Term Preview", bold=True, size=10, margin=(0,0,2,0)))
            preview_frame = QFrame()
            preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
            preview_frame.setMinimumHeight(70)
            preview_frame.setStyleSheet("background-color: white; border-radius: 4px;")
            preview_layout = QVBoxLayout(preview_frame)
            # Initialize preview label with current config values
            self.preview_label = PreviewLabel(
                border_style=config.get("border_style", "solid"),
                border_thickness=config.get("border_thickness", 1),
                border_color=config.get("border_color", "#0db5be")
            )
            preview_layout.addWidget(self.preview_label)
            appearance_layout.addWidget(preview_frame)
            appearance_layout.addWidget(PrettyLabel(
                "This shows a live preview of how your term underlines will appear.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            # --- Tooltip Button Colors (move below term preview) ---
            appearance_layout.addWidget(PrettyLabel("Tooltip Button Background", bold=True, size=10, margin=(0,0,2,0)))
            tooltip_bg_layout = QHBoxLayout()
            self.tooltip_bg_sample = QPushButton("")
            self.tooltip_bg_sample.setFixedSize(40, 30)
            self.tooltip_bg_sample.setStyleSheet(
                f"background-color: {config.get('tooltip_btn_bg', '#0db5be')}; border: 1px solid #aaa;"
            )
            self.tooltip_btn_bg = config.get("tooltip_btn_bg", "#0db5be")
            self.tooltip_bg_sample.clicked.connect(self.choose_tooltip_bg)
            self.tooltip_bg_value = QLineEdit()
            self.tooltip_bg_value.setText(self.tooltip_btn_bg)
            self.tooltip_bg_value.setFixedWidth(100)
            self.tooltip_bg_value.textChanged.connect(self.update_tooltip_bg_from_text)
            tooltip_bg_layout.addWidget(self.tooltip_bg_sample)
            tooltip_bg_layout.addWidget(self.tooltip_bg_value)
            tooltip_bg_layout.addStretch()
            appearance_layout.addLayout(tooltip_bg_layout)
            appearance_layout.addWidget(PrettyLabel(
                "Choose the background color for the tooltip button.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            appearance_layout.addWidget(PrettyLabel("Tooltip Button Text Color", bold=True, size=10, margin=(0,0,2,0)))
            tooltip_fg_layout = QHBoxLayout()
            self.tooltip_fg_sample = QPushButton("")
            self.tooltip_fg_sample.setFixedSize(40, 30)
            self.tooltip_fg_sample.setStyleSheet(
                f"background-color: {config.get('tooltip_btn_fg', '#fff')}; border: 1px solid #aaa;"
            )
            self.tooltip_btn_fg = config.get("tooltip_btn_fg", "#fff")
            self.tooltip_fg_sample.clicked.connect(self.choose_tooltip_fg)
            self.tooltip_fg_value = QLineEdit()
            self.tooltip_fg_value.setText(self.tooltip_btn_fg)
            self.tooltip_fg_value.setFixedWidth(100)
            self.tooltip_fg_value.textChanged.connect(self.update_tooltip_fg_from_text)
            tooltip_fg_layout.addWidget(self.tooltip_fg_sample)
            tooltip_fg_layout.addWidget(self.tooltip_fg_value)
            tooltip_fg_layout.addStretch()
            appearance_layout.addLayout(tooltip_fg_layout)
            appearance_layout.addWidget(PrettyLabel(
                "Choose the text color for the tooltip button.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            # --- Tooltip Button Preview (move after tooltip text color) ---
            appearance_layout.addWidget(PrettyLabel("Button Preview", bold=True, size=10, margin=(0,0,2,0)))
            self.tooltip_button_preview = TooltipButtonPreview(
                bg=config.get("tooltip_btn_bg", "#0db5be"),
                fg=config.get("tooltip_btn_fg", "#fff")
            )
            appearance_layout.addWidget(self.tooltip_button_preview)
            appearance_layout.addWidget(PrettyLabel(
                "This shows a live preview of how your tooltip button will appear.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            appearance_layout.addStretch()
            appearance_scroll.setWidget(appearance_container)
            tabs.addTab(appearance_scroll, "Appearance")

            # --- Blocked Words Tab ---
            blocked_words_tab = QWidget()
            blocked_words_scroll = QScrollArea()
            blocked_words_scroll.setWidgetResizable(True)
            blocked_words_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            blocked_words_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            blocked_words_container = QWidget()
            blocked_words_layout = QVBoxLayout(blocked_words_container)
            blocked_words_layout.setContentsMargins(24, 24, 24, 24)
            blocked_words_layout.setSpacing(18)

            # --- Blocked Words Tab ---
            blocked_words_layout.addWidget(PrettyLabel("Blocked Words", bold=True, size=10, margin=(0,0,2,0)))
            self.blocked_words = QPlainTextEdit()
            self.blocked_words.setPlainText(", ".join(config.get("blocked_words", [])))
            self.blocked_words.setMinimumHeight(80)
            self.blocked_words.setMaximumHeight(200)
            self.blocked_words.setPlaceholderText("Enter comma-separated words to block")
            self.blocked_words.setStyleSheet("""
                QPlainTextEdit {
                    font-size: 11pt;
                    padding: 8px 12px;
                }
            """)
            blocked_words_layout.addWidget(self.blocked_words)
            blocked_words_layout.addWidget(PrettyLabel(
                "Blocks tooltips for any phrase that contains the word, for example blocking apple will also block green apple, apple pie, and apple tree; you can also block specific two- or three-word phrases like apple pie or green apple (without affecting the individual words).",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            blocked_words_layout.addWidget(PrettyLabel("Blocked Unigrams", bold=True, size=10, margin=(0,0,2,0)))
            self.blocked_unigrams = QPlainTextEdit()
            self.blocked_unigrams.setPlainText(", ".join(config.get("blocked_unigrams", [])))
            self.blocked_unigrams.setMinimumHeight(80)
            self.blocked_unigrams.setMaximumHeight(200)
            self.blocked_unigrams.setPlaceholderText("Enter comma-separated unigrams to block")
            self.blocked_unigrams.setStyleSheet("""
                QPlainTextEdit {
                    font-size: 11pt;
                    padding: 8px 12px;
                }
            """)
            blocked_words_layout.addWidget(self.blocked_unigrams)
            blocked_words_layout.addWidget(PrettyLabel(
                "Blocks tooltips only when the word appears on its own, for example blocking apple will still allow tooltips for green apple and apple pie.",
                size=10, color="#666", margin=(0,0,12,0)
            ))

            blocked_words_layout.addStretch()
            blocked_words_scroll.setWidget(blocked_words_container)
            tabs.addTab(blocked_words_scroll, "Blocked Words")

            # --- About Tab (NEW) ---
            about_tab = QWidget()
            about_layout = QVBoxLayout(about_tab)
            about_layout.setContentsMargins(24, 24, 24, 24)
            about_layout.setSpacing(18)
            about_layout.addWidget(PrettyLabel("About Ankipedia", bold=True, size=10, margin=(0,0,8,0)))
            about_label = QLabel(
                "<b>Ankipedia</b> is an Anki addon that adds helpful Wikipedia pop-ups to terms in your flashcards, making it easy to understand unfamiliar concepts while you study. Just hover over underlined words during reviews to see short definitions and images — no extra clicks or effort needed.<br>  <br>For feature requests (including new Wikipedia language options), bug reports, or to contribute, please visit the GitHub repository: <a href='https://github.com/ctrlaltwill/ankipedia'>https://github.com/ctrlaltwill/ankipedia</a>.<br><br>"
                "Created by <a href='https://www.linkedin.com/in/williamguy/'>William Guy</a>. If you find this addon helpful, consider supporting development.<br><br>"
                            )
            about_label.setOpenExternalLinks(True)
            about_label.setWordWrap(True)
            about_layout.addWidget(about_label)

            # Add Buy Me a Coffee button with custom styling
            bmc_btn = QPushButton("☕ Buy me a coffee")
            bmc_btn.setFixedSize(217, 52)
            bmc_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffcc4d;
                    color: #000000;
                    border: 1px solid #000000;
                    border-radius: 4px;
                    font-family: Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 0;
                    padding-left: 30px;
                    padding-right: 30px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #FFDD00;
                }
            """)
            bmc_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            bmc_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.buymeacoffee.com/williamguy")))

            bmc_container = QWidget()
            bmc_layout = QHBoxLayout(bmc_container)
            bmc_layout.addStretch()
            bmc_layout.addWidget(bmc_btn)
            bmc_layout.addStretch()
            about_layout.addWidget(bmc_container)

            about_layout.addStretch()
            tabs.addTab(about_tab, "About")

            # --- Buttons ---
            btn_layout = QHBoxLayout()
            self.ok_btn = QPushButton("Save")
            self.cancel_btn = QPushButton("Cancel")
            btn_layout.addWidget(self.ok_btn)
            btn_layout.addWidget(self.cancel_btn)
            main_layout.addLayout(btn_layout)

            self.ok_btn.clicked.connect(self.accept)
            self.cancel_btn.clicked.connect(self.reject)

            # Fix Save button color (always blue)
            self.ok_btn.setStyleSheet("""
                QPushButton {
                    background: #0db5be;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 4px;
                    font-size: 13px;
                    min-width: 100px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #0ca3ac;
                }
            """)
            self.cancel_btn.setObjectName("cancel")  # For styling

            # Add shadow to preview frames
            preview_frame.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #eee;
                    border-radius: 8px;
                    padding: 16px;
                }
            """)

            # Style tooltips better
            label_style = """
                QLabel {
                    color: #444;
                    font-size: 13px;
                }
            """
            for label in self.findChildren(QLabel):
                label.setStyleSheet(label_style)

            # Make section headings stand out
            heading_style = """
                QLabel {
                    color: #222;
                    font-size: 14px;
                    font-weight: bold;
                    padding-top: 8px;
                }
            """
            for label in self.findChildren(PrettyLabel):
                if label.font().bold():
                    label.setStyleSheet(heading_style)

            # Initialize previews with default values
            self.update_preview()  # Set initial term preview
            self.update_tooltip_button_preview()  # Set initial button preview

            self.lang_combo.clear()
            itemDelegate = QStyledItemDelegate()
            self.lang_combo.setItemDelegate(itemDelegate)
            for code, name, _ in WIKI_LANGS:
                flag_path = FLAG_PATHS.get(code)
                if flag_path:
                    abs_flag_path = os.path.join(os.path.dirname(__file__), flag_path)
                    if os.path.exists(abs_flag_path):
                        pixmap = QPixmap(abs_flag_path)
                        # Scale the flag maintaining aspect ratio and keeping circular shape
                        pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        icon = QIcon(pixmap)
                        self.lang_combo.addItem(icon, f"  {name} ({code})", userData=code)  # Add padding after icon
                    else:
                        self.lang_combo.addItem(f"{name} ({code})", userData=code)
                else:
                    self.lang_combo.addItem(f"{name} ({code})", userData=code)
            idx = next((i for i in range(self.lang_combo.count())
                        if self.lang_combo.itemData(i) == config.get("wikipedia_lang", "en")), 0)
            self.lang_combo.setCurrentIndex(idx)

        def update_color_from_text(self):
            """Update color sample when text is changed manually"""
            color_text = self.color_value.text()
            if color_text.startswith('#') and (len(color_text) == 4 or len(color_text) == 7):
                self.border_color = color_text
                self.color_sample.setStyleSheet(f"background-color: {self.border_color}; border: 1px solid #aaa;")
                self.update_preview()

        def choose_color(self):
            """Open color picker dialog"""
            color = QColorDialog.getColor(QColor(self.border_color), self, "Choose Border Color")
            if color.isValid():
                self.border_color = color.name()
                self.color_sample.setStyleSheet(f"background-color: {self.border_color}; border: 1px solid #aaa;")
                self.color_value.setText(self.border_color)
                self.update_preview()

        def update_tooltip_bg_from_text(self):
            color_text = self.tooltip_bg_value.text()
            if color_text.startswith('#') and (len(color_text) == 4 or len(color_text) == 7):
                self.tooltip_btn_bg = color_text
                self.tooltip_bg_sample.setStyleSheet(f"background-color: {self.tooltip_btn_bg}; border: 1px solid #aaa;")
                self.update_tooltip_button_preview()

        def choose_tooltip_bg(self):
            color = QColorDialog.getColor(QColor(self.tooltip_btn_bg), self, "Choose Tooltip Button Background Color")
            if color.isValid():
                self.tooltip_btn_bg = color.name()
                self.tooltip_bg_sample.setStyleSheet(f"background-color: {self.tooltip_btn_bg}; border: 1px solid #aaa;")
                self.tooltip_bg_value.setText(self.tooltip_btn_bg)
                self.update_tooltip_button_preview()

        def update_tooltip_fg_from_text(self):
            color_text = self.tooltip_fg_value.text()
            if color_text.startswith('#') and (len(color_text) == 4 or len(color_text) == 7):
                self.tooltip_btn_fg = color_text
                self.tooltip_fg_sample.setStyleSheet(f"background-color: {self.tooltip_btn_fg}; border: 1px solid #aaa;")
                self.update_tooltip_button_preview()

        def choose_tooltip_fg(self):
            color = QColorDialog.getColor(QColor(self.tooltip_btn_fg), self, "Choose Tooltip Button Text Color")
            if color.isValid():
                self.tooltip_btn_fg = color.name()
                self.tooltip_fg_sample.setStyleSheet(f"background-color: {self.tooltip_btn_fg}; border: 1px solid #aaa;")
                self.tooltip_fg_value.setText(self.tooltip_btn_fg)
                self.update_tooltip_button_preview()

        def update_preview(self):
            """Update the preview label with current settings"""
            selected_border_style = next(btn for btn in self.border_style_group.buttons() if btn.isChecked()).property("style_id")
            border_thickness = self.thickness_slider.value() / 4
            self.preview_label.update_style(
                border_style=selected_border_style,
                border_thickness=border_thickness,
                border_color=self.border_color
            )

        def update_tooltip_button_preview(self):
            self.tooltip_button_preview.update_style(self.tooltip_btn_bg, self.tooltip_btn_fg)

        def restore_defaults(self):
            # Set all appearance settings to defaults
            # theme: light, border: 1px solid #0db5be, button bg: #0db5be, button fg: #fff
            theme_found = False
            for btn in self.theme_group.buttons():
                if btn.property("theme_id") == "light":
                    btn.setChecked(True)
                    theme_found = True
            
            # Fallback if light theme not found
            if not theme_found and self.theme_group.buttons():
                self.theme_group.buttons()[0].setChecked(True)
            
            for btn in self.border_style_group.buttons():
                btn.setChecked(btn.property("style_id") == "solid")
            
            self.thickness_slider.setValue(4)
            self.thickness_value_label.setText("1 px")
            self.color_value.setText("#0db5be")
            self.border_color = "#0db5be"
            self.color_sample.setStyleSheet("background-color: #0db5be; border: 1px solid #aaa;")
            # Removed cursor_style_group reset (no longer exists)
            self.tooltip_bg_value.setText("#0db5be")
            self.tooltip_btn_bg = "#0db5be"
            self.tooltip_bg_sample.setStyleSheet("background-color: #0db5be; border: 1px solid #aaa;")
            self.tooltip_fg_value.setText("#fff")
            self.tooltip_btn_fg = "#fff"
            self.tooltip_fg_sample.setStyleSheet("background-color: #fff; border: 1px solid #aaa;")
            self.update_preview()
            self.update_tooltip_button_preview()

        def get_values(self):
            # Add error handling to avoid StopIteration
            try:
                selected_theme = next(btn for btn in self.theme_group.buttons() if btn.isChecked())
                theme_id = selected_theme.property("theme_id")
            except StopIteration:
                # Fallback to "light" if no theme is selected
                theme_id = "light"
                
            selected_border_style = next(btn for btn in self.border_style_group.buttons() if btn.isChecked())
            blocked_words = [w.strip() for w in self.blocked_words.toPlainText().split(",") if w.strip()]
            blocked_unigrams = [u.strip() for u in self.blocked_unigrams.toPlainText().split(",") if u.strip()]
            return {
                "wikipedia_lang": self.lang_combo.currentData(),
                "class_name": self.class_edit.text(),
                "theme": theme_id,
                "border_style": selected_border_style.property("style_id"),
                "border_thickness": self.thickness_slider.value() / 4,
                "border_color": self.border_color,
                "tooltip_btn_bg": self.tooltip_btn_bg,
                "tooltip_btn_fg": self.tooltip_btn_fg,
                "blocked_words": blocked_words,
                "blocked_unigrams": blocked_unigrams
            }

    dlg = ConfigDialog(mw)
    if dlg.exec():
        # Get the previous theme to check if it changed
        previous_theme = config.get("theme", "auto")
        
        vals = dlg.get_values()
        config["wikipedia_lang"] = vals["wikipedia_lang"]
        config["class_name"] = vals["class_name"]
        config["theme"] = vals["theme"]
        config["border_style"] = vals["border_style"]
        config["border_thickness"] = vals["border_thickness"]
        config["border_color"] = vals["border_color"]
        config["tooltip_btn_bg"] = vals["tooltip_btn_bg"]
        config["tooltip_btn_fg"] = vals["tooltip_btn_fg"]
        config["blocked_words"] = vals["blocked_words"]
        config["blocked_unigrams"] = vals["blocked_unigrams"]
        mw.addonManager.writeConfig(__name__, config)
        
        # --- Refresh reviewer webview to apply new CSS immediately ---
        if hasattr(mw, "reviewer") and mw.reviewer and hasattr(mw.reviewer, "web"):
            try:
                # Update theme attribute in JS first, then reload
                update_theme_js = f"""
                (function() {{
                    // Update the JS variable for theme
                    window.ANKIPEDIA_THEME = "{vals['theme']}";
                    
                    // Update the HTML attribute
                    const html = document.documentElement;
                    if ("{vals['theme']}" === "auto") {{
                        html.setAttribute("data-ankipedia-theme", "auto");
                        const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
                        html.setAttribute("data-ankipedia-theme-system", isDark ? "dark" : "light");
                    }} else {{
                        html.setAttribute("data-ankipedia-theme", "{vals['theme']}");
                        html.removeAttribute("data-ankipedia-theme-system");
                    }}
                }})();
                """
                mw.reviewer.web.eval(update_theme_js)
                # mw.reviewer.web.reload()  # <-- Remove or comment out this line to prevent reset
            except Exception as e:
                print(f"Ankipedia: Failed to update theme: {e}")

def add_config_menu():
    from aqt import mw
    from aqt.qt import QAction
    action = QAction("Ankipedia Options...", mw)
    action.triggered.connect(show_config_dialog)
    mw.form.menuTools.addAction(action)

add_config_menu()