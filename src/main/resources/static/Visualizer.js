// Main visualization controller
let currentStep = 0;
let steps = [];
let widgets = {}; // Map widget ID to widget element
const API_BASE = 'http://localhost:8080/api';

/**
 * Run code visualization
 */
async function runVisualization() {
    const code = document.getElementById('codeEditor').value;

    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, input: "" })
        });

        const result = await response.json();

        if (result.output) {
            document.getElementById('consoleOutput').innerText = result.output;
        }

        steps = result.steps || [];
        currentStep = 0;
        widgets = {};

        // Clear canvas
        document.getElementById('vizBody').innerHTML = '';
        document.getElementById('callStackContainer').innerHTML = '';

        if (steps.length > 0) {
            render();
        } else {
            document.getElementById('stepInfo').innerHTML = 'No visualization steps generated.';
        }
    } catch (error) {
        console.error('Error running visualization:', error);
        document.getElementById('stepInfo').innerHTML = `<strong>Error:</strong> ${error.message}`;
    }
}

/**
 * Render current step
 */
function render() {
    if (steps.length === 0) return;

    const step = steps[currentStep];
    const vizBody = document.getElementById('vizBody');
    const stepInfo = document.getElementById('stepInfo');
    const callStackContainer = document.getElementById('callStackContainer');

    // Update step info
    stepInfo.innerHTML = `<strong>Line ${step.line}:</strong> ${step.description}`;
    document.getElementById('stepCounter').innerText = `${currentStep + 1} / ${steps.length}`;

    // Render call stack
    if (step.callStack) {
        const frames = step.callStack.split(' -> ').reverse();
        callStackContainer.innerHTML = frames
            .map(f => `<div class="stack-frame-pill">${escapeHtml(f)}</div>`)
            .join('');
    }

    // Track which variables are active in this step
    const activeVars = new Set(Object.keys(step.variables));

    // Remove widgets no longer in scope
    Object.keys(widgets).forEach(key => {
        if (!activeVars.has(key)) {
            const widget = widgets[key];
            widget.style.opacity = '0';
            widget.style.transform = 'scale(0.8)';
            setTimeout(() => {
                if (widget.parentNode) {
                    widget.parentNode.removeChild(widget);
                }
            }, 300);
            delete widgets[key];
        }
    });

    // Create or update widgets
    let yOffset = 80;
    let xOffset = 20;
    let index = 0;

    Object.entries(step.variables).forEach(([name, data]) => {
        let widget = widgets[name];

        if (!widget) {
            // Create new widget
            widget = createWidget(name, data);
            vizBody.appendChild(widget);
            widgets[name] = widget;

            // Position widget
            widget.style.left = `${xOffset}px`;
            widget.style.top = `${yOffset + (index * 90)}px`;

            // Trigger animation
            setTimeout(() => widget.classList.add('widget-show'), 10);
        } else {
            // Update existing widget
            updateWidget(widget, name, data);
        }

        index++;
    });
}

/**
 * Create widget based on type
 */
function createWidget(name, data) {
    const widget = document.createElement('div');
    widget.className = `viz-widget ${getWidgetClass(data.type)}`;
    widget.id = `widget-${name}`;

    updateWidget(widget, name, data);

    return widget;
}

/**
 * Update widget content
 */
function updateWidget(widget, name, data) {
    const widgetType = data.widgetType || getWidgetType(data.type);

    let content = `
        <div class="widget-header">
            <span>${escapeHtml(name)}</span>
            <span class="widget-type">${escapeHtml(data.type)}</span>
        </div>
    `;

    if (widgetType === 'array') {
        content += renderArrayWidget(data.value);
    } else if (widgetType === 'object' || widgetType === 'dictionary') {
        content += renderObjectWidget(data.value);
    } else if (widgetType === 'string') {
        content += renderStringWidget(data.value);
    } else {
        content += `<div class="widget-value">${escapeHtml(data.value)}</div>`;
    }

    if (widget.innerHTML !== content) {
        widget.innerHTML = content;
        // Add highlight effect on update
        widget.classList.add('widget-highlight');
        setTimeout(() => widget.classList.remove('widget-highlight'), 300);
    }
}

/**
 * Render array widget
 */
function renderArrayWidget(value) {
    const values = value.split(',').map(v => v.trim());
    const cells = values.map((v, i) => `
        <div class="array-cell" title="Index ${i}">
            ${escapeHtml(v)}
            <div class="array-index">[${i}]</div>
        </div>
    `).join('');

    return `<div class="array-cells">${cells}</div>`;
}

/**
 * Render string widget
 */
function renderStringWidget(value) {
    const chars = value.split('').map((c, i) => `
        <div class="array-cell" title="Index ${i}">
            ${escapeHtml(c === ' ' ? '·' : c)}
        </div>
    `).join('');

    return `<div class="array-cells">${chars}</div>`;
}

/**
 * Render object/dictionary widget
 */
function renderObjectWidget(value) {
    // Try to parse as JSON if it looks like an object
    try {
        const obj = typeof value === 'string' ? JSON.parse(value) : value;
        const entries = Object.entries(obj).map(([k, v]) => `
            <div style="margin: 4px 0; padding: 4px; background: rgba(0,0,0,0.2); border-radius: 4px;">
                <span style="color: var(--accent-orange);">${escapeHtml(k)}:</span>
                <span style="color: white;">${escapeHtml(String(v))}</span>
            </div>
        `).join('');
        return `<div style="margin-top: 8px;">${entries}</div>`;
    } catch {
        return `<div class="widget-value">${escapeHtml(String(value))}</div>`;
    }
}

/**
 * Get widget CSS class based on type
 */
function getWidgetClass(type) {
    if (type === 'ARRAY') return 'array';
    if (type.includes('Map') || type === 'OBJECT') return 'object';
    return 'variable';
}

/**
 * Get widget type for rendering
 */
function getWidgetType(type) {
    if (type === 'ARRAY') return 'array';
    if (type === 'String') return 'string';
    if (type.includes('Map') || type === 'OBJECT') return 'object';
    return 'variable';
}

/**
 * Navigation functions
 */
function nextStep() {
    if (currentStep < steps.length - 1) {
        currentStep++;
        render();
    }
}

function prevStep() {
    if (currentStep > 0) {
        currentStep--;
        render();
    }
}

/**
 * Reset editor
 */
function resetEditor() {
    document.getElementById('codeEditor').value = '';
    document.getElementById('vizBody').innerHTML = '';
    document.getElementById('stepInfo').innerText = 'Ready to visualize.';
    document.getElementById('stepCounter').innerText = '0 / 0';
    document.getElementById('consoleOutput').innerText = '';
    document.getElementById('callStackContainer').innerHTML = '';
    steps = [];
    currentStep = 0;
    widgets = {};
}

/**
 * Toggle theme
 */
function toggleTheme() {
    document.body.style.filter = document.body.style.filter ? "" : "invert(1) hue-rotate(180deg)";
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Keyboard shortcuts
 */
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
        if (e.key === 'Enter') {
            e.preventDefault();
            runVisualization();
        } else if (e.key === 'r') {
            e.preventDefault();
            resetEditor();
        }
    } else if (e.key === 'ArrowLeft') {
        prevStep();
    } else if (e.key === 'ArrowRight') {
        nextStep();
    }
});

/**
 * Auto-resize textarea
 */
const codeEditor = document.getElementById('codeEditor');
codeEditor.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = this.scrollHeight + 'px';
});

/**
 * Initialize
 */
window.addEventListener('load', () => {
    console.log('Frosted Java Visualizer initialized');
    document.getElementById('stepInfo').innerText = 'Ready to visualize. Write your code and click Run.';
});