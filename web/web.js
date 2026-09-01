// ── Scan root resolution
function getScanRoot() {
  if (window.ANKIPEDIA_SELECTOR) {
    try {
      const el = document.querySelector(window.ANKIPEDIA_SELECTOR);
      if (el) return el;
    } catch (e) {
      console.warn("Invalid ANKIPEDIA_SELECTOR, falling back to default");
    }
  }

  return document.querySelector("#qa") || document.body;
}

document.addEventListener('DOMContentLoaded', () => {
  const style = document.createElement('style');
  style.textContent = `
    .ankipediaTerm {
      position: relative;
      display: inline-block;
      border-bottom: none !important; /* Remove default border */
    }
    .ankipediaTerm::after {
      content: '';
      position: absolute;
      left: 0;
      right: 0;
      bottom: -1px;  /* Position the border slightly higher */
      border-bottom: ${window.ANKIPEDIA_BORDER_THICKNESS}px ${window.ANKIPEDIA_BORDER_STYLE} ${window.ANKIPEDIA_BORDER_COLOR};
      transform: translateY(-1px); /* Offset up by 1px */
    }
  `;
  document.head.appendChild(style);

  let observer;
  const tooltipsAdded = [];
  const maxConcurrentQueries = 100; // Maximum number of concurrent Wikipedia queries

  // ── Provider state ──
  const configuredProvider = window.ANKIPEDIA_DEFAULT_PROVIDER || 'wikipedia';
  let currentProvider = (configuredProvider === 'jisho' || configuredProvider === 'wikipedia')
      ? configuredProvider
      : 'wikipedia';

  // ── Centralized cache (null-prototype to avoid prototype pollution) ──
  const definitionCache = {
      wikipedia: Object.create(null),
      jisho: Object.create(null)
  };

  // These arrays will now be populated from config
  const blockedUnigrams = window.ANKIPEDIA_BLOCKED_UNIGRAMS || [];
  const blockedWords = window.ANKIPEDIA_BLOCKED_WORDS || [];

  // Get the Wikipedia language and class name from the injected variables, default to 'en' and 'ankipedia'
  const WIKI_LANG = window.ANKIPEDIA_WIKI_LANG || 'en';
  const ANKIPEDIA_CLASS_NAME = window.ANKIPEDIA_CLASS_NAME || 'ankipedia';

  const applyTooltips = (ankipediaElement, isBody = false) => {
    const tooltipAppliedFlag = 'tooltips-applied';

    const originalHtml = ankipediaElement.innerHTML;
    let html = originalHtml;

    const extractCandidateTerms = (html) => {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
    
      const getTextOutsideTooltips = (node) => {
        let text = '';
        const walker = document.createTreeWalker(
          node,
          NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
          {
            acceptNode: (node) => {
              if (node.nodeType === Node.TEXT_NODE) return NodeFilter.FILTER_ACCEPT;
              if (node.hasAttribute && node.hasAttribute('data-tooltip')) return NodeFilter.FILTER_REJECT;
              return NodeFilter.FILTER_SKIP;
            }
          }
        );
    
        let currentNode;
        while (currentNode = walker.nextNode()) {
          if (currentNode.nodeType === Node.TEXT_NODE) {
            text += currentNode.textContent + ' ';
          }
        }
        return text;
      };
    
      const text = getTextOutsideTooltips(doc.body);
      
      // New text processing that preserves possessives
      const words = text.trim()
      // Convert any fancy quotes to simple quotes
      .replace(/['’′]/g, "'")
      // Remove punctuation except apostrophes and hyphens
      .replace(/[^\w\s'-]/g, ' ')
      // Remove extra spaces around hyphens
      .replace(/\s*-\s*/g, '-')
      // Remove apostrophes not in the middle or end of words
      .replace(/\B'\B/g, '') // remove isolated apostrophes
      .replace(/\s+/g, ' ')
      .split(' ')
      .map(word => word.toLowerCase())
      .filter(w => w.length > 2);
    
      const unigrams = words.filter(word => !blockedUnigrams.includes(word));
      const bigrams = [];
      const trigrams = [];

      // Create bigrams and trigrams
      for (let i = 0; i < words.length - 1; i++) {
        const bigram = words.slice(i, i + 2).join(' ');
        if (bigram.length > 5) {
          bigrams.push(bigram);
        }
        
        if (i < words.length - 2) {
          const trigram = words.slice(i, i + 3).join(' ');
          if (trigram.length > 8) {
            trigrams.push(trigram);
          }
        }
      }

      return {
        unigrams: [...new Set(unigrams)],
        bigrams: [...new Set(bigrams)],
        trigrams: [...new Set(trigrams)]
      };
    };

const decodeHTMLEntities = (text) => {
  const textarea = document.createElement('textarea');
  textarea.innerHTML = text;
  return textarea.value;
};

const sanitizeWikipediaContent = (content) => {
  if (!content) return '';
  
  // First remove any HTML tags
  const plainText = content.replace(/<[^>]*>/g, '');
  
  // Decode HTML entities to actual characters
  return decodeHTMLEntities(plainText);
};

// ── Wikipedia fetcher (pure, no cache) ──
const queryWikipedia = async (term) => {
  try {
    const res = await fetch(`https://${WIKI_LANG}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(term)}`);
    const data = await res.json();

    if (res.status === 404 || !data.extract || data.type === 'disambiguation') {
      return null;
    }

    const sanitizedExtract = sanitizeWikipediaContent(data.extract);
    console.log(`Successfully fetched Wikipedia article for: "${term}"`);

    return {
      source: 'wikipedia',
      definition: sanitizedExtract,
      html: '', // no rich HTML for Wikipedia
      thumbnail: data.thumbnail ? data.thumbnail.source : null,
      desktopUrl: data.content_urls?.desktop?.page || null,
    };
  } catch (err) {
    return null;
  }
};

// ── Provider router (owns cache) ──
async function fetchDefinition(term) {
  const provider = currentProvider;
  const cacheKey = term.toLowerCase();

  // Check cache
  if (definitionCache[provider] && definitionCache[provider][cacheKey]) {
    return definitionCache[provider][cacheKey];
  }

  let result = null;

  if (provider === 'wikipedia') {
    result = await queryWikipedia(term);
  } else if (provider === 'jisho') {
      result = await fetchJisho(term);
  } else {
      console.warn(`Unknown definition provider: ${provider}`);
      return null;
  }

  // Cache successful results only
  if (result) {
    definitionCache[provider][cacheKey] = result;
  }

  return result;
}

// ── Provider setter (state only – Phase 5 adds reparse) ──
function setProvider(provider) {
  if (provider !== 'wikipedia' && provider !== 'jisho') return;
  currentProvider = provider;
}

// ── Jisho request registry ──
const jishoRequests = new Map();
let nextJishoRequestId = 0;

// ── Jisho bridge callback (called from Python) ──
window.__jisho_resolve = function(requestId, envelope) {
    if (!jishoRequests.has(requestId)) {
        console.warn(`Jisho request ${requestId} not found (already resolved or timed out)`);
        return;
    }

    const entry = jishoRequests.get(requestId);
    clearTimeout(entry.timeoutId);
    jishoRequests.delete(requestId);

    // Resolve the Promise
    entry.resolve(envelope);
};

// ── Jisho bridge client ──
function fetchJisho(term) {
    return new Promise((resolve) => {
        const requestId = `jisho_${++nextJishoRequestId}`;

        const timeoutId = setTimeout(() => {
            if (jishoRequests.has(requestId)) {
                jishoRequests.delete(requestId);
                resolve(null); // ← changed: ProviderResult | null only
            }
        }, 6000);

        jishoRequests.set(requestId, {
            resolve: (envelope) => {
                // Normalize the raw envelope to ProviderResult
                resolve(normalizeJishoResult(envelope, term));
            },
            timeoutId: timeoutId
        });

        const payload = JSON.stringify({
            action: 'lookup',
            request_id: requestId,
            query: term
        });

        if (typeof pycmd === 'function') {
            pycmd('jisho:' + payload);
        } else {
            clearTimeout(timeoutId);
            jishoRequests.delete(requestId);
            resolve(null);
        }
    });
}

const processTermsInBatches = async (terms) => {
  const results = [];
  const failedTerms = [];
  const successfulTerms = new Set();

  for (let i = 0; i < terms.length; i += maxConcurrentQueries) {
    const batch = terms.slice(i, i + maxConcurrentQueries);
    const batchResults = await Promise.all(
      batch.map(term =>
        fetchDefinition(term).then(result => {
          if (result) {
            successfulTerms.add(term.toLowerCase());
          } else {
            failedTerms.push(term);
          }
          return result;
        }).catch(() => {
          failedTerms.push(term);
          return null;
        })
      )
    );
    results.push(...batchResults);
  }

  if (failedTerms.length > 0) {
    console.warn('Failed to fetch the following terms:', failedTerms);
  }
  console.log('Terms with successful results:', [...successfulTerms]);

  return { results, successfulTerms };
};

const escapeHTML = (str) => {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
};

// ── Build rich Jisho HTML from normalized data ──
function buildJishoHTML(first) {
    const japanese = first.japanese?.[0] || {};
    const word = escapeHTML(japanese.word || '');
    const reading = escapeHTML(japanese.reading || '');

    const meanings = first.senses
        .map(s => escapeHTML((s.english_definitions || []).join(', ')))
        .filter(Boolean)
        .join('<br>');

    const parts = escapeHTML(
        first.senses[0]?.parts_of_speech?.join(', ') || ''
    );

    let html = `<strong>${word}</strong>`;

    if (reading) {
        html += ` <span style="color:#888;font-size:0.9em;">(${reading})</span>`;
    }

    if (meanings) {
        html += `<br>${meanings}`;
    }

    if (parts) {
        html += `<br><em style="color:#999;font-size:0.8em;">${parts}</em>`;
    }

    return html;
}

// ── Normalize raw Jisho API response to ProviderResult ──
function normalizeJishoResult(envelope, term) {
    // Reject failed envelopes
    if (!envelope.ok || !envelope.data) {
        return null;
    }

    const data = envelope.data;
    if (!data.data || data.data.length === 0) {
        return null;
    }

    const first = data.data[0];
    const japanese = first.japanese?.[0] || {};
    const word = japanese.word || term;

    // Build plain-text definition
    const definition = first.senses
        .flatMap(s => s.english_definitions || [])
        .join('; ');

    if (!definition) {
        return null;
    }

    return {
        source: 'jisho',
        definition: definition,
        html: buildJishoHTML(first),
        thumbnail: null,
        desktopUrl: `https://jisho.org/search/${encodeURIComponent(word)}`
    };
}

const addTooltipSpans = async (termGroups) => {
  let updatedHtml = html;
  const rangesUsed = [];
  const usedWords = new Set();
  const ankipediaTermsAdded = []; // Array to track terms with .ankipediaTerm added

  const overlapsExistingTooltip = (index, length) => {
    return rangesUsed.some(([start, end]) => index < end && index + length > start);
  };

  const isInsideExistingAnkipediaTerm = (index, termLength) => {
    const range = document.createRange();
    let currentNode = ankipediaElement.firstChild;
    let currentOffset = 0;

    // Traverse the child nodes to find the correct node for the given index
    while (currentNode && currentOffset + currentNode.textContent.length <= index) {
      currentOffset += currentNode.textContent.length;
      currentNode = currentNode.nextSibling;
    }

    // If no valid node is found, return false
    if (!currentNode || !currentNode.textContent) return false;

    // Calculate the relative offset within the found node
    const relativeIndex = index - currentOffset;

    // Ensure the offset is within the bounds of the node
    if (relativeIndex < 0 || relativeIndex + termLength > currentNode.textContent.length) {
      return false;
    }

    try {
      // Set the range and check if it is inside a .ankipediaTerm element
      range.setStart(currentNode, relativeIndex);
      range.setEnd(currentNode, relativeIndex + termLength);

      const container = range.commonAncestorContainer;
      return container.nodeType === 1 && container.closest('.ankipediaTerm') !== null;
    } catch (e) {
      // Handle any unexpected errors gracefully
      console.error('Error in isInsideExistingAnkipediaTerm:', e);
      return false;
    }
  };

  const processTerms = async (terms) => {
    const { results, successfulTerms } = await processTermsInBatches(terms);
    const termsWithTooltips = new Set();

    for (let i = 0; i < terms.length; i++) {
      const term = terms[i];
      if (blockedWords.some(word => term.toLowerCase().includes(word))) continue;

      const words = term.split(' ');
      if (words.every(w => usedWords.has(w))) continue;

      const result = results[i];
      if (!result) continue;

      const { definition, thumbnail, desktopUrl } = result;

      const escaped = term.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
      // --- FIX: handle apostrophes in terms ---
      // If the term contains an apostrophe, do not use \b word boundaries
      let regex;
      if (term.includes("'")) {
        regex = new RegExp(
          `(${escaped})(?!(?=[^<]*>))(?!(?=[^<]*data-tooltip))`,
          'gi'
        );
      } else {
        regex = new RegExp(
          `\\b(${escaped})\\b(?!(?=[^<]*>))(?!(?=[^<]*data-tooltip))`,
          'gi'
        );
      }
      // --- END FIX ---

      // --- NEW: Normalize apostrophes in updatedHtml before replace ---
      updatedHtml = updatedHtml
        .replace(/&#39;|&apos;|’|‘|′/g, "'"); // normalize all apostrophe variants to '

      updatedHtml = updatedHtml.replace(regex, (match, p1, offset) => {
        const termLower = p1.toLowerCase();
        
        // Check if we're inside a tooltip attribute
        const beforeMatch = updatedHtml.substring(0, offset);
        if (beforeMatch.lastIndexOf('data-tooltip="') > beforeMatch.lastIndexOf('">')) {
          console.log(`Term skipped (inside tooltip): ${termLower}`);
          return match; // Skip if we're inside a tooltip
        }

        if (
          overlapsExistingTooltip(offset, p1.length) ||
          isInsideExistingAnkipediaTerm(offset, p1.length) ||
          ankipediaTermsAdded.includes(termLower)
        ) {
          console.log(`Term skipped (overlapping tooltip): ${termLower}`);
          return match;
        }

        rangesUsed.push([offset, offset + p1.length]);
        words.forEach(w => usedWords.add(w));

        // Add the term to the ankipediaTermsAdded array if not already added
        ankipediaTermsAdded.push(termLower);

        const tooltipHtml = `<span class="ankipediaTerm underline" 
                  data-term="${escapeHTML(p1)}" 
                  data-tooltip="${escapeHTML(definition)}" 
                  data-html="${escapeHTML(result.html || '')}"
                  data-source="${escapeHTML(result.source || 'wikipedia')}"
                  data-thumbnail="${escapeHTML(thumbnail || '')}" 
                  data-url="${escapeHTML(desktopUrl || '')}">
                  ${p1}
              </span>`;

        termsWithTooltips.add(termLower);
        return tooltipHtml;
      });
    }

    // After processing, compare what terms got tooltips vs what had Wikipedia results
    console.log('Terms that had Wikipedia results but no tooltips added:', 
      [...successfulTerms].filter(term => !termsWithTooltips.has(term)));
  };

  await processTerms(termGroups.trigrams);
  await processTerms(termGroups.bigrams);
  await processTerms(termGroups.unigrams);

  ankipediaElement.innerHTML = updatedHtml;
  ankipediaElement.setAttribute('data-tooltips-applied', 'true');

  console.log(`Number of <span class="ankipediaTerm"> added: ${ankipediaElement.querySelectorAll('.ankipediaTerm').length}`);
  console.log('Tooltips added:', tooltipsAdded);
  console.log('AnkipediaTerms added:', ankipediaTermsAdded); // Log the terms with .ankipediaTerm added

  // Initialize tooltips and context menus for the added .ankipediaTerm elements
  initTooltips();
  initContextMenus();
};

    const initTooltips = () => {
      // Set to track terms that have already had a tooltip applied (case insensitive)
      const processedTerms = new Set();
    
      // Helper function to check if an element is inside another element with a 'ankipediaTerm' class
      const isInsideAnkipediaTerm = (el) => {
        return el.closest('.ankipediaTerm') !== null;
      };
    
      // First, process all the text-based 'ankipediaTerm' elements
      document.querySelectorAll('.ankipediaTerm').forEach(el => {
        const term = el.textContent.trim().toLowerCase(); // Normalize to lowercase
    
        // Skip if this term has already been processed or the element is inside another 'ankipediaTerm'
        if (processedTerms.has(term) || isInsideAnkipediaTerm(el)) {
          return;  // Skip if this term has already had a tooltip or is inside an existing 'ankipediaTerm'
        }
    
        // Add this term to the set to track it (case insensitive)
        processedTerms.add(term);
    
        // Initialize Tippy.js for valid elements
        const tooltip = tippy(el, {
          content: (reference) => {
            const source = reference.getAttribute('data-source') || 'wikipedia';
            const tooltipContent = reference.getAttribute('data-tooltip') || 'No definition found';
            const htmlContent = reference.getAttribute('data-html') || '';
            const thumbnail = reference.getAttribute('data-thumbnail');
            const url = reference.getAttribute('data-url');

            if (source === 'jisho' && htmlContent) {
              const wrapper = document.createElement('div');
              wrapper.className = 'tooltip-content';
              wrapper.innerHTML = htmlContent;

              if (url) {
                const linkDiv = document.createElement('div');
                linkDiv.style.cssText = 'margin-top: 0.5em;';
                const link = document.createElement('a');
                link.href = url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.style.cssText = 'font-size: 0.85em; color: #0db5be !important;';
                link.textContent = 'Open in Jisho →';
                linkDiv.appendChild(link);
                wrapper.appendChild(linkDiv);
              }

              return wrapper;
            }

            // Wikipedia: existing plain-text rendering
            const content = document.createElement('div');
            content.className = 'tooltip-content';

            if (thumbnail) {
              const img = document.createElement('img');
              img.src = thumbnail;
              img.alt = reference.getAttribute('data-term');
              content.appendChild(img);
            }

            const textDiv = document.createElement('div');
            textDiv.className = 'tooltip-text';

            const text = document.createElement('p');
            text.textContent = tooltipContent;
            textDiv.appendChild(text);

            if (url) {
              const link = document.createElement('a');
              link.href = url;
              link.target = '_blank';
              link.rel = 'noopener noreferrer';
              link.textContent = 'Read more on Wikipedia';
              textDiv.appendChild(link);
            }

            content.appendChild(textDiv);
            return content;
          },
          allowHTML: true,
          delay: [500, 200],
          theme: 'light',
          interactive: true,
          placement: 'bottom',
          hideOnClick: false,
        });
      });
    
      // Then, process all the image elements with alt attributes
      document.querySelectorAll('img[alt]').forEach(img => {
        const altText = img.alt.trim().toLowerCase(); // Normalize to lowercase
    
        // Skip if this alt text term has already been processed or the image is inside another 'ankipediaTerm'
        if (processedTerms.has(altText) || isInsideAnkipediaTerm(img)) {
          return;  // Skip if this alt text term has already had a tooltip or is inside an existing 'ankipediaTerm'
        }
    
        // Add this term to the set to track it (case insensitive)
        processedTerms.add(altText);
    
        // Initialize Tippy.js with 'manual' trigger for valid elements
        const tooltip = tippy(img, {
          content: (reference) => {
            const source = reference.getAttribute('data-source') || 'wikipedia';
            const tooltipContent = reference.getAttribute('data-tooltip') || 'No definition found';
            const htmlContent = reference.getAttribute('data-html') || '';
            const thumbnail = reference.getAttribute('data-thumbnail');
            const url = reference.getAttribute('data-url');

            if (source === 'jisho' && htmlContent) {
              const wrapper = document.createElement('div');
              wrapper.className = 'tooltip-content';
              wrapper.innerHTML = htmlContent;
              return wrapper;
            }

            const content = document.createElement('div');
            content.className = 'tooltip-content';

            if (thumbnail) {
              const imageTag = document.createElement('img');
              imageTag.src = thumbnail;
              imageTag.alt = reference.getAttribute('data-term');
              content.appendChild(imageTag);
            }

            const textDiv = document.createElement('div');
            textDiv.className = 'tooltip-text';

            const text = document.createElement('p');
            text.textContent = tooltipContent;
            textDiv.appendChild(text);

            if (url) {
              const link = document.createElement('a');
              link.href = url;
              link.target = '_blank';
              link.rel = 'noopener noreferrer';
              link.textContent = source === 'jisho' ? 'Open in Jisho →' : 'Read more on Wikipedia';
              textDiv.appendChild(link);
            }

            content.appendChild(textDiv);
            return content;
          },
          allowHTML: true,
          delay: [500, 200],
          theme: 'light',
          interactive: true,
          placement: 'bottom',
          hideOnClick: false,
        });
      });
    };
    
    

    

    
    
    
    
    

    
    
    
    
    

    const run = async () => {
      const termGroups = extractCandidateTerms(ankipediaElement.innerText);
      console.log('Candidate terms:', termGroups);
      await addTooltipSpans(termGroups);
      initTooltips();
    };

    run();
  };

  const watchForAnkipedia = () => {
    const ankipediaElement = getScanRoot();
    const isBody = (ankipediaElement === document.body);
    
    console.log('Ankipedia scan root:', ankipediaElement);
    
    applyTooltips(ankipediaElement, isBody);
    
    // Initialize context menus after tooltips are applied
    setTimeout(initContextMenus, 1000);

    if (observer) observer.disconnect();

    observer = new MutationObserver(() => {
        const root = getScanRoot();
        const isBody = (root === document.body);
        if (root && root.getAttribute('data-tooltips-applied') !== 'true') {
            console.log('Detected new content, applying tooltips.');
            applyTooltips(root, isBody);
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
  };

  document.body.setAttribute('data-ankipedia-theme', window.ANKIPEDIA_THEME || 'auto');
  
  if (typeof tippy === 'undefined') {
    const p = document.createElement('script');
    p.src = 'https://unpkg.com/@popperjs/core@2';
    p.onload = () => {
      const s = document.createElement('script');
      s.src = 'https://unpkg.com/tippy.js@6';
      s.onload = () => {
        watchForAnkipedia();
        // Add observer for theme changes
        const themeObserver = new MutationObserver(() => {
          document.body.setAttribute('data-ankipedia-theme', window.ANKIPEDIA_THEME || 'auto');
        });
        themeObserver.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ['data-ankipedia-theme']
        });
      };
      document.head.appendChild(s);
    };
    document.head.appendChild(p);
  } else {
    watchForAnkipedia();
  }
});

// Add theme change listener
if (window.ANKIPEDIA_THEME === "auto") {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', event => {
    document.documentElement.setAttribute('data-ankipedia-theme-system', event.matches ? 'dark' : 'light');
  });
}

// Add context menu for blocking words/unigrams
document.addEventListener("contextmenu", function (e) {
    const root = getScanRoot();
    if (!root || !root.contains(e.target)) return;
    
    let selection = window.getSelection();
    let selectedText = selection ? selection.toString().trim() : "";
    if (!selectedText || selectedText.split(/\s+/).length > 3) return; // Only allow up to 3 words

    // Check if selection contains an ankipediaTerm
    let hasAnkipediaTerm = false;
    let ankipediaSpan = null;
    if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const container = range.commonAncestorContainer;
        ankipediaSpan = container.nodeType === 1 ? 
            container.closest('.ankipediaTerm') : 
            container.parentElement.closest('.ankipediaTerm');
        hasAnkipediaTerm = !!ankipediaSpan;
    }

    // Remove any existing menu
    let oldMenu = document.getElementById("ankipedia-block-menu");
    if (oldMenu) oldMenu.remove();

    // Create menu with updated styling
    let menu = document.createElement("div");
    menu.id = "ankipedia-block-menu";
    menu.style.position = "fixed";
    menu.style.left = e.clientX + "px";
    menu.style.top = e.clientY + "px";
    menu.style.background = "#fff";
    menu.style.border = "none";
    menu.style.borderRadius = "4px";
    menu.style.boxShadow = "0 0 20px 4px rgba(154, 161, 177, 0.15), 0 4px 80px -8px rgba(36, 40, 47, 0.25), 0 4px 4px -2px rgba(91, 94, 105, 0.15)";
    menu.style.zIndex = 999999;
    menu.style.fontSize = "14px";
    menu.style.minWidth = "180px";
    menu.style.cursor = "pointer";
    menu.style.userSelect = "none";
    menu.style.padding = "0.5em 0";

    // Theme-aware background for block menu
    let theme = (document.documentElement.getAttribute("data-ankipedia-theme") || "auto");
    let systemTheme = document.documentElement.getAttribute("data-ankipedia-theme-system");
    if (
        theme === "dark" ||
        (theme === "auto" && systemTheme === "dark")
    ) {
        menu.style.background = "#2c2c2c";
        menu.style.color = "#fff";
        menu.style.border = "1px solid #444";
    } else {
        menu.style.background = "#fff";
        menu.style.color = "#000";
        menu.style.border = "1px solid #ccc";
    }

    function addMenuItem(label, cb) {
        let item = document.createElement("div");
        item.textContent = label;
        item.style.padding = "8px 18px";
        item.onmouseenter = () => {
            if (
                theme === "dark" ||
                (theme === "auto" && systemTheme === "dark")
            ) {
                item.style.background = "#4a4a4a";
            } else {
                item.style.background = "#f0f0f0";
            }
        };
        item.onmouseleave = () => item.style.background = "";
        item.onmousedown = () => {
            if (
                theme === "dark" ||
                (theme === "auto" && systemTheme === "dark")
            ) {
                item.style.background = "#555";
            } else {
                item.style.background = window.ANKIPEDIA_TOOLTIP_BTN_BG || "#0db5be";
            }
            item.style.color = window.ANKIPEDIA_TOOLTIP_BTN_FG || "#fff";
        };
        item.onmouseup = () => {
            // Restore hover color after click
            if (
                theme === "dark" ||
                (theme === "auto" && systemTheme === "dark")
            ) {
                item.style.background = "#4a4a4a";
            } else {
                item.style.background = "#f0f0f0";
            }
            item.style.color = "";
        };
        item.onclick = async function() {
            await cb();
            menu.remove();
        };
        menu.appendChild(item);
    }

    // Add Copy option
    addMenuItem("Copy", async function() {
        try {
            await navigator.clipboard.writeText(selectedText);
        } catch (err) {
            const textarea = document.createElement("textarea");
            textarea.value = selectedText;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand("copy");
            } catch (err) {
                console.error("Copy failed:", err);
            }
            document.body.removeChild(textarea);
        }
    });

    // Add blocking options that also remove formatting
    if (hasAnkipediaTerm && ankipediaSpan) {
        addMenuItem("Add to Blocked Words", async function() {
            if (typeof pycmd !== 'undefined') {
                // Send command and wait for response
                await pycmd(`ankipedia:block:word:${selectedText}`);
                // Remove the ankipediaTerm formatting
                const parent = ankipediaSpan.parentNode;
                const text = ankipediaSpan.textContent;
                parent.replaceChild(document.createTextNode(text), ankipediaSpan);
                // Do NOT reload the page
            }
        });

        // Only show "Add to Blocked Unigrams" if single word
        if (selectedText.split(/\s+/).length === 1) {
            addMenuItem("Add to Blocked Unigrams", async function() {
                if (typeof pycmd !== 'undefined') {
                    // Send command and wait for response
                    await pycmd(`ankipedia:block:unigram:${selectedText}`);
                    // Remove the ankipediaTerm formatting
                    const parent = ankipediaSpan.parentNode;
                    const text = ankipediaSpan.textContent;
                    parent.replaceChild(document.createTextNode(text), ankipediaSpan);
                    // Do NOT reload the page
                }
            });
        }
    }

    document.body.appendChild(menu);

    // Remove menu on click elsewhere 
    document.addEventListener("mousedown", function handler(ev) {
        if (!menu.contains(ev.target)) {
            menu.remove();
            document.removeEventListener("mousedown", handler);
        }
    });

    e.preventDefault();
}, true);

// Initialize context menu handlers
function initContextMenus() {
    document.querySelectorAll('.ankipediaTerm').forEach(term => {
        // Remove existing listeners to prevent duplicates
        term.removeEventListener('contextmenu', handleContextMenu);
        // Add fresh listener
        term.addEventListener('contextmenu', handleContextMenu);
    });
}

// Updated handleContextMenu to match the text selection right-click menu design
function handleContextMenu(event) {
    event.preventDefault();
    const term = event.target;
    const termText = term.getAttribute('data-term').toLowerCase();
    
    // Remove any existing menu
    let oldMenu = document.getElementById("ankipedia-block-menu");
    if (oldMenu) oldMenu.remove();
    
    // Create menu with updated styling (same as the text selection menu)
    let menu = document.createElement("div");
    menu.id = "ankipedia-block-menu";
    menu.style.position = "fixed";
    menu.style.left = event.clientX + "px";
    menu.style.top = event.clientY + "px";
    menu.style.background = "#fff";
    menu.style.border = "none";
    menu.style.borderRadius = "4px";
    menu.style.boxShadow = "0 0 20px 4px rgba(154, 161, 177, 0.15), 0 4px 80px -8px rgba(36, 40, 47, 0.25), 0 4px 4px -2px rgba(91, 94, 105, 0.15)";
    menu.style.zIndex = 999999;
    menu.style.fontSize = "14px";
    menu.style.minWidth = "180px";
    menu.style.cursor = "pointer";
    menu.style.userSelect = "none";
    menu.style.padding = "0.5em 0";

    // Theme-aware background for block menu
    let theme = (document.documentElement.getAttribute("data-ankipedia-theme") || "auto");
    let systemTheme = document.documentElement.getAttribute("data-ankipedia-theme-system");
    if (
        theme === "dark" ||
        (theme === "auto" && systemTheme === "dark")
    ) {
        menu.style.background = "#2c2c2c !important";
        menu.style.color = "#fff";
        menu.style.border = "1px solid #444";
    } else {
        menu.style.background = "#fff";
        menu.style.color = "#444";
        menu.style.border = "1px solid #ccc";
    }
    
    function addMenuItem(label, cb) {
        let item = document.createElement("div");
        item.textContent = label;
        item.style.padding = "8px 18px";
        item.onmouseenter = () => {
            if (
                theme === "dark" ||
                (theme === "auto" && systemTheme === "dark")
            ) {
                item.style.background = "#3a3a3a";
            } else {
                item.style.background = "#f0f0f0";
            }
        };
        item.onmouseleave = () => item.style.background = "";
        item.onmousedown = () => {
            if (
                theme === "dark" ||
                (theme === "auto" && systemTheme === "dark")
            ) {
                item.style.background = "#4a4a4a";
            } else {
                item.style.background = window.ANKIPEDIA_TOOLTIP_BTN_BG || "#0db5be";
            }
            item.style.color = window.ANKIPEDIA_TOOLTIP_BTN_FG || "#fff";
        };
        item.onmouseup = () => {
            // Restore hover color after click
            if (
                theme === "dark" ||
                (theme === "auto" && systemTheme === "dark")
            ) {
                item.style.background = "#4a4a4a";
            } else {
                item.style.background = "#f0f0f0";
            }
            item.style.color = "#000";
        };
        item.onclick = async function() {
            await cb();
            menu.remove();
        };
        menu.appendChild(item);
    }
    
    // Add Copy option
    addMenuItem("Copy", async function() {
        try {
            await navigator.clipboard.writeText(termText);
        } catch (err) {
            const textarea = document.createElement("textarea");
            textarea.value = termText;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand("copy");
            } catch (err) {
                console.error("Copy failed:", err);
            }
            document.body.removeChild(textarea);
        }
    });
    
    // Add block word option
    addMenuItem("Add to Blocked Words", async function() {
        if (typeof pycmd !== 'undefined') {
            await pycmd(`ankipedia:block:word:${termText}`);
            // Remove the ankipediaTerm span after blocking
            const parent = term.parentNode;
            const text = term.textContent;
            parent.replaceChild(document.createTextNode(text), term);
        }
    });
    
    // Add block unigram option for single words
    if (termText.split(/\s+/).length === 1) {
        addMenuItem("Add to Blocked Unigrams", async function() {
            if (typeof pycmd !== 'undefined') {
                await pycmd(`ankipedia:block:unigram:${termText}`);
                // Remove the ankipediaTerm span after blocking
                const parent = term.parentNode;
                const text = term.textContent;
                parent.replaceChild(document.createTextNode(text), term);
            }
        });
    }
    
    document.body.appendChild(menu);
    
    // Remove menu on click elsewhere
    document.addEventListener("mousedown", function handler(ev) {
        if (!menu.contains(ev.target)) {
            menu.remove();
            document.removeEventListener("mousedown", handler);
        }
    });
}

// Make sure to call initContextMenus after tooltips are applied
document.addEventListener('DOMContentLoaded', function() {
    // ...existing code...
    
    // Add observer to initialize context menus when new content is loaded
    const observer = new MutationObserver((mutations) => {
        for (let mutation of mutations) {
            if (mutation.type === 'childList' && mutation.addedNodes.length) {
                // Small delay to ensure all tooltips are applied
                setTimeout(() => {
                    initContextMenus();
                }, 500);
            }
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // ...existing code...
});
