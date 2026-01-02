package com.frosted.visualizer.model;

import java.util.*;

/**
 * Represents a single frame on the call stack
 */
public class CallFrame {
    private String name;
    private List<String> nodes; // Code lines/statements
    private int lineno;
    private int instructionPointer;
    private Map<String, Object> locals;
    private Map<String, String> variableWidgets; // Variable name -> Widget ID mapping
    private String scopeWidgetId;
    private Map<String, Object> iterators; // For loop tracking
    private int recursionLevel;
    private List<Object> callArgs;
    private Object returnValue;
    private boolean isRecursiveCall;
    private String callTraceWidgetId;

    public CallFrame(String name, List<String> nodes, int lineno, int recursionLevel, List<Object> callArgs) {
        this.name = name;
        this.nodes = nodes != null ? nodes : new ArrayList<>();
        this.lineno = lineno;
        this.instructionPointer = 0;
        this.locals = new HashMap<>();
        this.variableWidgets = new HashMap<>();
        this.iterators = new HashMap<>();
        this.recursionLevel = recursionLevel;
        this.callArgs = callArgs != null ? callArgs : new ArrayList<>();
        this.isRecursiveCall = recursionLevel > 0;
    }

    public CallFrame(String name, List<String> nodes) {
        this(name, nodes, 0, 0, null);
    }

    // Getters and Setters
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public List<String> getNodes() { return nodes; }
    public void setNodes(List<String> nodes) { this.nodes = nodes; }

    public int getLineno() { return lineno; }
    public void setLineno(int lineno) { this.lineno = lineno; }

    public int getInstructionPointer() { return instructionPointer; }
    public void setInstructionPointer(int ip) { this.instructionPointer = ip; }
    public void incrementIP() { this.instructionPointer++; }

    public Map<String, Object> getLocals() { return locals; }
    public void setLocals(Map<String, Object> locals) { this.locals = locals; }

    public Map<String, String> getVariableWidgets() { return variableWidgets; }
    public void setVariableWidgets(Map<String, String> widgets) { this.variableWidgets = widgets; }

    public String getScopeWidgetId() { return scopeWidgetId; }
    public void setScopeWidgetId(String id) { this.scopeWidgetId = id; }

    public Map<String, Object> getIterators() { return iterators; }
    public void setIterators(Map<String, Object> iterators) { this.iterators = iterators; }

    public int getRecursionLevel() { return recursionLevel; }
    public void setRecursionLevel(int level) { this.recursionLevel = level; }

    public List<Object> getCallArgs() { return callArgs; }
    public void setCallArgs(List<Object> args) { this.callArgs = args; }

    public Object getReturnValue() { return returnValue; }
    public void setReturnValue(Object value) { this.returnValue = value; }

    public boolean isRecursiveCall() { return isRecursiveCall; }
    public void setRecursiveCall(boolean recursive) { this.isRecursiveCall = recursive; }

    public String getCallTraceWidgetId() { return callTraceWidgetId; }
    public void setCallTraceWidgetId(String id) { this.callTraceWidgetId = id; }

    public boolean hasMoreInstructions() {
        return instructionPointer < nodes.size();
    }
}