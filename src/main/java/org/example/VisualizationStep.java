package com.frosted.visualizer.model;

import java.util.HashMap;
import java.util.Map;

/**
 * Represents a single step in code execution visualization
 */
public class VisualizationStep {
    private int line;
    private String description;
    private Map<String, VariableState> variables;
    private String callStack;
    private String highlight;
    private String frameType; // "variable", "scope", "print", "array", etc.
    private Map<String, Object> metadata;

    public VisualizationStep(int line, String description, Map<String, VariableState> variables) {
        this.line = line;
        this.description = description;
        this.variables = variables != null ? variables : new HashMap<>();
        this.callStack = "";
        this.highlight = "";
        this.metadata = new HashMap<>();
    }

    // Getters and Setters
    public int getLine() { return line; }
    public void setLine(int line) { this.line = line; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public Map<String, VariableState> getVariables() { return variables; }
    public void setVariables(Map<String, VariableState> variables) { this.variables = variables; }

    public String getCallStack() { return callStack; }
    public void setCallStack(String callStack) { this.callStack = callStack; }

    public String getHighlight() { return highlight; }
    public void setHighlight(String highlight) { this.highlight = highlight; }

    public String getFrameType() { return frameType; }
    public void setFrameType(String frameType) { this.frameType = frameType; }

    public Map<String, Object> getMetadata() { return metadata; }
    public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }

    public static class VariableState {
        private String type;
        private String value;
        private Map<String, Object> metadata;
        private String widgetType; // "variable", "array", "object", "string", etc.

        public VariableState(String type, String value) {
            this.type = type;
            this.value = value;
            this.metadata = new HashMap<>();
        }

        public String getType() { return type; }
        public void setType(String type) { this.type = type; }

        public String getValue() { return value; }
        public void setValue(String value) { this.value = value; }

        public Map<String, Object> getMetadata() { return metadata; }
        public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }

        public String getWidgetType() { return widgetType; }
        public void setWidgetType(String widgetType) { this.widgetType = widgetType; }
    }
}