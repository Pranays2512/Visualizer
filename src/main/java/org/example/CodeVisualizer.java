package org.example;

public class CodeVisualizer package com.frosted.visualizer.service;

import com.frosted.visualizer.model.*;
        import com.github.javaparser.*;
        import com.github.javaparser.ast.*;
        import com.github.javaparser.ast.body.*;
        import com.github.javaparser.ast.expr.*;
        import com.github.javaparser.ast.stmt.*;

        import java.util.*;

/**
 * Main code visualization engine - analyzes and executes code step by step
 */
public class CodeVisualizer {
    private String code;
    private List<VisualizationStep> steps;
    private Deque<CallFrame> callStack;
    private Map<String, MethodDeclaration> methods;
    private StringBuilder consoleOutput;
    private RecursionTracker recursionTracker;
    private int stepCount;
    private static final int MAX_STEPS = 2000;
    private boolean inExpressionEvaluation;

    public CodeVisualizer(String code, String input) {
        this.code = code;
        this.steps = new ArrayList<>();
        this.callStack = new ArrayDeque<>();
        this.methods = new HashMap<>();
        this.consoleOutput = new StringBuilder();
        this.recursionTracker = new RecursionTracker();
        this.stepCount = 0;
        this.inExpressionEvaluation = false;
    }

    public List<VisualizationStep> analyze() {
        try {
            CompilationUnit cu = StaticJavaParser.parse(code);

            // Index all methods
            cu.findAll(MethodDeclaration.class).forEach(m ->
                    methods.put(m.getNameAsString(), m)
            );

            // Find main method
            MethodDeclaration main = methods.get("main");
            if (main != null) {
                executeMethod(main, new ArrayList<>());
            } else {
                recordStep(0, "No main method found", new HashMap<>());
            }

        } catch (Exception e) {
            recordStep(0, "Error: " + e.getMessage(), new HashMap<>());
        }
        return steps;
    }

    private Object executeMethod(MethodDeclaration method, List<Object> args) {
        if (stepCount++ > MAX_STEPS) {
            throw new RuntimeException("Execution limit exceeded");
        }

        String methodName = method.getNameAsString();

        // Check recursion limit
        if (!recursionTracker.canRecurse(methodName)) {
            return recursionTracker.getBaseCaseValue(methodName, args);
        }

        int recursionLevel = recursionTracker.startCall(methodName, args);

        // Create new stack frame
        CallFrame frame = new CallFrame(methodName, new ArrayList<>(),
                method.getBegin().map(p -> p.line).orElse(0),
                recursionLevel, args);

        // Bind parameters
        List<Parameter> params = method.getParameters();
        for (int i = 0; i < params.size(); i++) {
            Parameter param = params.get(i);
            if (i < args.size()) {
                frame.getLocals().put(param.getNameAsString(), args.get(i));
            }
        }

        callStack.push(frame);

        int line = method.getBegin().map(p -> p.line).orElse(0);
        recordStep(line, "Entering " + methodName, frame.getLocals());

        Object returnValue = null;
        if (method.getBody().isPresent()) {
            try {
                executeStatement(method.getBody().get());
            } catch (ReturnException re) {
                returnValue = re.value;
            }
        }

        callStack.pop();
        recursionTracker.endCall(methodName, returnValue);

        return returnValue;
    }

    private void executeStatement(Statement stmt) {
        if (stepCount++ > MAX_STEPS) return;

        int line = stmt.getBegin().map(p -> p.line).orElse(0);

        if (stmt.isBlockStmt()) {
            for (Statement s : stmt.asBlockStmt().getStatements()) {
                executeStatement(s);
            }
        } else if (stmt.isExpressionStmt()) {
            executeExpression(stmt.asExpressionStmt().getExpression());
            recordStep(line, "Executed expression", getCurrentFrame().getLocals());
        } else if (stmt.isIfStmt()) {
            handleIfStatement(stmt.asIfStmt(), line);
        } else if (stmt.isReturnStmt()) {
            handleReturnStatement(stmt.asReturnStmt(), line);
        } else if (stmt.isForStmt()) {
            handleForLoop(stmt.asForStmt());
        } else if (stmt.isWhileStmt()) {
            handleWhileLoop(stmt.asWhileStmt());
        }
    }

    private void handleIfStatement(IfStmt ifStmt, int line) {
        recordStep(line, "Checking condition: " + ifStmt.getCondition(), getCurrentFrame().getLocals());
        Object condition = evaluateExpression(ifStmt.getCondition());

        if (Boolean.TRUE.equals(condition)) {
            executeStatement(ifStmt.getThenStmt());
        } else if (ifStmt.getElseStmt().isPresent()) {
            executeStatement(ifStmt.getElseStmt().get());
        }
    }

    private void handleReturnStatement(ReturnStmt returnStmt, int line) {
        recordStep(line, "Return statement", getCurrentFrame().getLocals());
        Object val = null;
        if (returnStmt.getExpression().isPresent()) {
            boolean wasInEval = inExpressionEvaluation;
            inExpressionEvaluation = true;
            try {
                val = evaluateExpression(returnStmt.getExpression().get());
            } finally {
                inExpressionEvaluation = wasInEval;
            }
        }
        throw new ReturnException(val);
    }

    private void handleForLoop(ForStmt forStmt) {
        // Initialize
        for (Expression init : forStmt.getInitialization()) {
            executeExpression(init);
        }

        // Loop
        while (true) {
            if (forStmt.getCompare().isPresent()) {
                Object cond = evaluateExpression(forStmt.getCompare().get());
                if (!Boolean.TRUE.equals(cond)) break;
            }
            executeStatement(forStmt.getBody());
            for (Expression update : forStmt.getUpdate()) {
                executeExpression(update);
            }
        }
    }

    private void handleWhileLoop(WhileStmt whileStmt) {
        while (true) {
            Object cond = evaluateExpression(whileStmt.getCondition());
            if (!Boolean.TRUE.equals(cond)) break;
            executeStatement(whileStmt.getBody());
        }
    }

    private Object executeExpression(Expression expr) {
        if (expr.isVariableDeclarationExpr()) {
            return handleVariableDeclaration(expr.asVariableDeclarationExpr());
        } else if (expr.isAssignExpr()) {
            return handleAssignment(expr.asAssignExpr());
        } else if (expr.isMethodCallExpr()) {
            return handleMethodCall(expr.asMethodCallExpr());
        } else if (expr.isUnaryExpr()) {
            return handleUnaryExpression(expr.asUnaryExpr());
        }
        return evaluateExpression(expr);
    }

    private Object handleVariableDeclaration(VariableDeclarationExpr vde) {
        for (VariableDeclarator vd : vde.getVariables()) {
            String name = vd.getNameAsString();
            Object value = null;
            if (vd.getInitializer().isPresent()) {
                value = evaluateExpression(vd.getInitializer().get());
            }
            updateVariable(name, value, vde.getElementType().toString());
        }
        return null;
    }

    private Object handleAssignment(AssignExpr assign) {
        Object value = evaluateExpression(assign.getValue());

        if (assign.getTarget().isArrayAccessExpr()) {
            ArrayAccessExpr access = assign.getTarget().asArrayAccessExpr();
            String name = access.getName().toString();
            Object indexObj = evaluateExpression(access.getIndex());
            int index = indexObj instanceof Integer ? (int)indexObj : 0;
            updateArrayVariable(name, index, value);
        } else {
            String target = assign.getTarget().toString();
            updateVariable(target, value, null);
        }
        return value;
    }

    private Object handleMethodCall(MethodCallExpr call) {
        String methodName = call.getNameAsString();
        List<Object> args = new ArrayList<>();
        for (Expression arg : call.getArguments()) {
            args.add(evaluateExpression(arg));
        }

        if (methods.containsKey(methodName)) {
            if (inExpressionEvaluation) {
                return callMethodDirectly(methodName, args);
            } else {
                return executeMethod(methods.get(methodName), args);
            }
        } else if (methodName.equals("print") || methodName.equals("println")) {
            for (Object arg : args) consoleOutput.append(arg);
            if (methodName.equals("println")) consoleOutput.append("\n");
        }
        return null;
    }

    private Object handleUnaryExpression(UnaryExpr unary) {
        if (unary.getOperator() == UnaryExpr.Operator.POSTFIX_INCREMENT) {
            String name = unary.getExpression().toString();
            Object val = getVariableValue(name);
            if (val instanceof Integer) {
                updateVariable(name, (int)val + 1, null);
                return val;
            }
        }
        return evaluateExpression(unary);
    }

    private Object callMethodDirectly(String methodName, List<Object> args) {
        // Direct execution for expression evaluation
        MethodDeclaration method = methods.get(methodName);
        if (method == null) return null;

        // Simple execution without visualization
        Map<String, Object> tempLocals = new HashMap<>();
        List<Parameter> params = method.getParameters();
        for (int i = 0; i < params.size() && i < args.size(); i++) {
            tempLocals.put(params.get(i).getNameAsString(), args.get(i));
        }

        // Execute method body (simplified)
        if (method.getBody().isPresent()) {
            for (Statement stmt : method.getBody().get().getStatements()) {
                if (stmt.isReturnStmt() && stmt.asReturnStmt().getExpression().isPresent()) {
                    return evaluateExpression(stmt.asReturnStmt().getExpression().get());
                }
            }
        }
        return null;
    }

    private Object evaluateExpression(Expression expr) {
        if (expr.isIntegerLiteralExpr()) {
            return expr.asIntegerLiteralExpr().asInt();
        }
        if (expr.isBooleanLiteralExpr()) {
            return expr.asBooleanLiteralExpr().getValue();
        }
        if (expr.isStringLiteralExpr()) {
            return expr.asStringLiteralExpr().asString();
        }
        if (expr.isNameExpr()) {
            return getVariableValue(expr.asNameExpr().getNameAsString());
        }
        if (expr.isArrayAccessExpr()) {
            ArrayAccessExpr access = expr.asArrayAccessExpr();
            String name = access.getName().toString();
            Object indexObj = evaluateExpression(access.getIndex());
            int index = indexObj instanceof Integer ? (int)indexObj : 0;
            return getArrayValue(name, index);
        }
        if (expr.isArrayInitializerExpr()) {
            List<Object> values = new ArrayList<>();
            for (Expression e : expr.asArrayInitializerExpr().getValues()) {
                values.add(evaluateExpression(e));
            }
            return values;
        }
        if (expr.isBinaryExpr()) {
            return evaluateBinaryExpression(expr.asBinaryExpr());
        }
        if (expr.isEnclosedExpr()) {
            return evaluateExpression(expr.asEnclosedExpr().getInner());
        }
        return null;
    }

    private Object evaluateBinaryExpression(BinaryExpr be) {
        Object left = evaluateExpression(be.getLeft());
        Object right = evaluateExpression(be.getRight());

        if (left instanceof Integer && right instanceof Integer) {
            int l = (int) left;
            int r = (int) right;
            switch(be.getOperator()) {
                case PLUS: return l + r;
                case MINUS: return l - r;
                case MULTIPLY: return l * r;
                case DIVIDE: return l / r;
                case LESS_EQUALS: return l <= r;
                case LESS: return l < r;
                case GREATER: return l > r;
                case GREATER_EQUALS: return l >= r;
                case EQUALS: return l == r;
            }
        }
        return null;
    }

    private CallFrame getCurrentFrame() {
        return callStack.peek();
    }

    private void updateVariable(String name, Object value, String type) {
        CallFrame frame = getCurrentFrame();
        if (frame != null) {
            frame.getLocals().put(name, value);
        }
    }

    private void updateArrayVariable(String name, int index, Object value) {
        CallFrame frame = getCurrentFrame();
        if (frame != null && frame.getLocals().containsKey(name)) {
            Object arr = frame.getLocals().get(name);
            if (arr instanceof List) {
                @SuppressWarnings("unchecked")
                List<Object> list = (List<Object>) arr;
                if (index >= 0 && index < list.size()) {
                    list.set(index, value);
                }
            }
        }
    }

    private Object getVariableValue(String name) {
        for (CallFrame frame : callStack) {
            if (frame.getLocals().containsKey(name)) {
                return frame.getLocals().get(name);
            }
        }
        return 0;
    }

    private Object getArrayValue(String name, int index) {
        Object arr = getVariableValue(name);
        if (arr instanceof List) {
            @SuppressWarnings("unchecked")
            List<Object> list = (List<Object>) arr;
            if (index >= 0 && index < list.size()) {
                return list.get(index);
            }
        }
        return 0;
    }

    private void recordStep(int line, String desc, Map<String, Object> locals) {
        Map<String, VisualizationStep.VariableState> vars = new HashMap<>();

        if (locals != null) {
            for (Map.Entry<String, Object> entry : locals.entrySet()) {
                String type = determineType(entry.getValue());
                String value = convertValueToString(entry.getValue());
                VisualizationStep.VariableState state = new VisualizationStep.VariableState(type, value);
                state.setWidgetType(determineWidgetType(entry.getValue()));
                vars.put(entry.getKey(), state);
            }
        }

        VisualizationStep step = new VisualizationStep(line, desc, vars);

        // Build call stack string
        StringBuilder sb = new StringBuilder();
        Iterator<CallFrame> it = callStack.descendingIterator();
        while(it.hasNext()) {
            sb.append(it.next().getName()).append(" -> ");
        }
        if (sb.length() > 4) {
            sb.setLength(sb.length() - 4);
        }
        step.setCallStack(sb.toString());

        steps.add(step);
    }

    private String determineType(Object value) {
        if (value instanceof List) return "ARRAY";
        if (value instanceof Map) return "OBJECT";
        if (value instanceof Integer) return "int";
        if (value instanceof String) return "String";
        if (value instanceof Boolean) return "boolean";
        return "UNKNOWN";
    }

    private String determineWidgetType(Object value) {
        if (value instanceof List) return "array";
        if (value instanceof Map) return "dictionary";
        if (value instanceof String) return "string";
        return "variable";
    }

    private String convertValueToString(Object value) {
        if (value instanceof List) {
            @SuppressWarnings("unchecked")
            List<Object> list = (List<Object>) value;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < list.size(); i++) {
                sb.append(list.get(i));
                if (i < list.size() - 1) sb.append(", ");
            }
            return sb.toString();
        }
        return String.valueOf(value);
    }

    public String getOutput() {
        return consoleOutput.toString();
    }

    private static class ReturnException extends RuntimeException {
        Object value;
        public ReturnException(Object value) {
            this.value = value;
        }
    }
}{
}
