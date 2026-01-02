package org.example;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;

import java.util.*;

public class CodeAnalyzer {
    private String code;
    private List<CodeExecutionController.VisualizationStep> steps;
    private Deque<StackFrame> callStack;
    private Map<String, MethodDeclaration> methods;
    private StringBuilder consoleOutput;
    private int stepCount = 0;
    private static final int MAX_STEPS = 2000;

    public CodeAnalyzer(String code, String input) {
        this.code = code;
        this.steps = new ArrayList<>();
        this.callStack = new ArrayDeque<>();
        this.methods = new HashMap<>();
        this.consoleOutput = new StringBuilder();
    }

    public List<CodeExecutionController.VisualizationStep> analyze() {
        try {
            CompilationUnit cu = StaticJavaParser.parse(code);
            
            // Index methods
            cu.findAll(MethodDeclaration.class).forEach(m -> 
                methods.put(m.getNameAsString(), m)
            );

            // Find main
            MethodDeclaration main = methods.get("main");
            if (main != null) {
                executeMethod(main, new ArrayList<>());
            } else {
                steps.add(new CodeExecutionController.VisualizationStep(0, "No main method found", new HashMap<>()));
            }

        } catch (Exception e) {
            // e.printStackTrace();
            steps.add(new CodeExecutionController.VisualizationStep(0, "Error: " + e.getMessage(), new HashMap<>()));
        }
        return steps;
    }

    private Object executeMethod(MethodDeclaration method, List<Object> args) {
        if (stepCount++ > MAX_STEPS) throw new RuntimeException("Execution limit exceeded");

        // Create new stack frame
        StackFrame frame = new StackFrame(method.getNameAsString());
        
        // Bind parameters
        for (int i = 0; i < method.getParameters().size(); i++) {
            Parameter param = method.getParameter(i);
            if (i < args.size()) {
                frame.variables.put(param.getNameAsString(), 
                    new CodeExecutionController.VariableState(param.getTypeAsString(), String.valueOf(args.get(i))));
            }
        }

        callStack.push(frame);
        
        int line = method.getBegin().map(p -> p.line).orElse(0);
        recordStep(line, "Entering " + method.getNameAsString());

        Object returnValue = null;
        if (method.getBody().isPresent()) {
            try {
                executeStatement(method.getBody().get());
            } catch (ReturnException re) {
                returnValue = re.value;
            }
        }

        callStack.pop();
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
            recordStep(line, "Executed expression");
        } else if (stmt.isIfStmt()) {
            IfStmt ifStmt = stmt.asIfStmt();
            recordStep(line, "Checking condition: " + ifStmt.getCondition());
            Object condition = evaluateExpression(ifStmt.getCondition());
            if (Boolean.TRUE.equals(condition)) {
                executeStatement(ifStmt.getThenStmt());
            } else if (ifStmt.getElseStmt().isPresent()) {
                executeStatement(ifStmt.getElseStmt().get());
            }
        } else if (stmt.isReturnStmt()) {
            ReturnStmt returnStmt = stmt.asReturnStmt();
            recordStep(line, "Return statement");
            Object val = null;
            if (returnStmt.getExpression().isPresent()) {
                val = evaluateExpression(returnStmt.getExpression().get());
            }
            throw new ReturnException(val);
        } else if (stmt.isForStmt()) {
            ForStmt forStmt = stmt.asForStmt();
            for (Expression init : forStmt.getInitialization()) executeExpression(init);
            while (true) {
                if (forStmt.getCompare().isPresent()) {
                    Object cond = evaluateExpression(forStmt.getCompare().get());
                    if (!Boolean.TRUE.equals(cond)) break;
                }
                executeStatement(forStmt.getBody());
                for (Expression update : forStmt.getUpdate()) executeExpression(update);
            }
        } else if (stmt.isWhileStmt()) {
            WhileStmt whileStmt = stmt.asWhileStmt();
            while (true) {
                Object cond = evaluateExpression(whileStmt.getCondition());
                if (!Boolean.TRUE.equals(cond)) break;
                executeStatement(whileStmt.getBody());
            }
        }
    }

    private Object executeExpression(Expression expr) {
        if (expr.isVariableDeclarationExpr()) {
            VariableDeclarationExpr vde = expr.asVariableDeclarationExpr();
            for (VariableDeclarator vd : vde.getVariables()) {
                String name = vd.getNameAsString();
                Object value = null;
                if (vd.getInitializer().isPresent()) {
                    value = evaluateExpression(vd.getInitializer().get());
                }
                
                if (value instanceof List) {
                    String valStr = value.toString().replace("[", "").replace("]", "");
                    getCurrentFrame().variables.put(name, 
                        new CodeExecutionController.VariableState("ARRAY", valStr));
                } else {
                    getCurrentFrame().variables.put(name, 
                        new CodeExecutionController.VariableState(vde.getElementType().toString(), String.valueOf(value)));
                }
            }
            return null;
        } else if (expr.isAssignExpr()) {
            AssignExpr assign = expr.asAssignExpr();
            Object value = evaluateExpression(assign.getValue());
            
            if (assign.getTarget().isArrayAccessExpr()) {
                ArrayAccessExpr access = assign.getTarget().asArrayAccessExpr();
                String name = access.getName().toString();
                Object indexObj = evaluateExpression(access.getIndex());
                int index = indexObj instanceof Integer ? (int)indexObj : 0;
                
                updateArrayVariable(name, index, value);
            } else {
                String target = assign.getTarget().toString();
                updateVariable(target, value);
            }
            return value;
        } else if (expr.isMethodCallExpr()) {
            MethodCallExpr call = expr.asMethodCallExpr();
            String methodName = call.getNameAsString();
            List<Object> args = new ArrayList<>();
            for (Expression arg : call.getArguments()) {
                args.add(evaluateExpression(arg));
            }
            
            if (methods.containsKey(methodName)) {
                return executeMethod(methods.get(methodName), args);
            } else if (methodName.equals("print") || methodName.equals("println")) {
                for (Object arg : args) consoleOutput.append(arg);
                if (methodName.equals("println")) consoleOutput.append("\n");
            }
            return null;
        } else if (expr.isUnaryExpr()) {
            UnaryExpr unary = expr.asUnaryExpr();
            if (unary.getOperator() == UnaryExpr.Operator.POSTFIX_INCREMENT) {
                String name = unary.getExpression().toString();
                Object val = getVariableValue(name);
                if (val instanceof Integer) {
                    updateVariable(name, (int)val + 1);
                    return val;
                }
            }
        }
        return evaluateExpression(expr);
    }

    private Object evaluateExpression(Expression expr) {
        if (expr.isIntegerLiteralExpr()) return expr.asIntegerLiteralExpr().asInt();
        if (expr.isBooleanLiteralExpr()) return expr.asBooleanLiteralExpr().getValue();
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
            BinaryExpr be = expr.asBinaryExpr();
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
        }
        if (expr.isEnclosedExpr()) {
            return evaluateExpression(expr.asEnclosedExpr().getInner());
        }
        return null;
    }

    private StackFrame getCurrentFrame() { return callStack.peek(); }
    
    private void updateVariable(String name, Object value) {
        for (StackFrame frame : callStack) {
            if (frame.variables.containsKey(name)) {
                CodeExecutionController.VariableState state = frame.variables.get(name);
                state.setValue(String.valueOf(value));
                return;
            }
        }
    }
    
    private void updateArrayVariable(String name, int index, Object value) {
        for (StackFrame frame : callStack) {
            if (frame.variables.containsKey(name)) {
                CodeExecutionController.VariableState state = frame.variables.get(name);
                if ("ARRAY".equals(state.getType())) {
                    String[] parts = state.getValue().split(",");
                    if (index >= 0 && index < parts.length) {
                        parts[index] = String.valueOf(value).trim();
                        state.setValue(String.join(", ", parts));
                    }
                }
                return;
            }
        }
    }

    private Object getVariableValue(String name) {
        for (StackFrame frame : callStack) {
            if (frame.variables.containsKey(name)) {
                String val = frame.variables.get(name).getValue();
                try { return Integer.parseInt(val.trim()); } catch(Exception e) { return val; }
            }
        }
        return 0;
    }
    
    private Object getArrayValue(String name, int index) {
        for (StackFrame frame : callStack) {
            if (frame.variables.containsKey(name)) {
                CodeExecutionController.VariableState state = frame.variables.get(name);
                if ("ARRAY".equals(state.getType())) {
                    String[] parts = state.getValue().split(",");
                    if (index >= 0 && index < parts.length) {
                        String val = parts[index].trim();
                        try { return Integer.parseInt(val); } catch(Exception e) { return val; }
                    }
                }
            }
        }
        return 0;
    }

    private void recordStep(int line, String desc) {
        Map<String, CodeExecutionController.VariableState> vars = new HashMap<>();
        if (!callStack.isEmpty()) {
            vars.putAll(getCurrentFrame().variables);
        }
        
        CodeExecutionController.VisualizationStep step = new CodeExecutionController.VisualizationStep(line, desc, deepCopyVariables(vars));
        
        StringBuilder sb = new StringBuilder();
        Iterator<StackFrame> it = callStack.descendingIterator();
        while(it.hasNext()) {
            sb.append(it.next().name).append(" -> ");
        }
        if (sb.length() > 4) sb.setLength(sb.length() - 4);
        step.setCallStack(sb.toString());
        
        steps.add(step);
    }
    
    private Map<String, CodeExecutionController.VariableState> deepCopyVariables(Map<String, CodeExecutionController.VariableState> original) {
        Map<String, CodeExecutionController.VariableState> copy = new HashMap<>();
        for (Map.Entry<String, CodeExecutionController.VariableState> entry : original.entrySet()) {
            CodeExecutionController.VariableState originalState = entry.getValue();
            CodeExecutionController.VariableState newState = new CodeExecutionController.VariableState(
                originalState.getType(), 
                originalState.getValue()
            );
            copy.put(entry.getKey(), newState);
        }
        return copy;
    }
    
    public String getOutput() {
        return consoleOutput.toString();
    }

    private static class StackFrame {
        String name;
        Map<String, CodeExecutionController.VariableState> variables = new HashMap<>();
        public StackFrame(String name) { this.name = name; }
    }

    private static class ReturnException extends RuntimeException {
        Object value;
        public ReturnException(Object value) { this.value = value; }
    }
}