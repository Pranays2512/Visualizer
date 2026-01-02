const Drawers = {
    // RECURSION: Draws nested frames representing the call stack
    renderRecursion: (container, stackData) => {
        container.innerHTML = '';
        stackData.forEach((frame, index) => {
            const frameDiv = document.createElement('div');
            frameDiv.className = `stack-frame ${index === stackData.length - 1 ? 'active' : ''}`;
            frameDiv.style.marginLeft = `${index * 20}px`;
            frameDiv.innerHTML = `
                <div class="frame-header">Method: ${frame.name}</div>
                <div class="frame-body">
                    ${Object.entries(frame.vars).map(([k, v]) => `
                        <div class="var-pill"><span>${k}</span><b>${v}</b></div>
                    `).join('')}
                </div>
            `;
            container.appendChild(frameDiv);
        });
    },

    // TREES: Uses SVG to draw nodes and smooth edges
    renderTree: (container, treeData) => {
        // Implementation for SVG tree with line connectors...
    }
};