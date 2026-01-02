package org.example;

public class RecursionTracker package


import java.util.*;

/**
 * Tracks recursive function calls and their relationships
 */
public class RecursionTracker {
    private Map<String, List<CallInfo>> callTree;
    private Map<String, Integer> currentCalls;
    private int maxDepth;

    public RecursionTracker() {
        this.callTree = new HashMap<>();
        this.currentCalls = new HashMap<>();
        this.maxDepth = 8;
    }

    public boolean canRecurse(String funcName) {
        int currentDepth = currentCalls.getOrDefault(funcName, 0);
        return currentDepth < maxDepth;
    }

    public int startCall(String funcName, List<Object> args) {
        int currentDepth = currentCalls.getOrDefault(funcName, 0);
        currentCalls.put(funcName, currentDepth + 1);

        if (!callTree.containsKey(funcName)) {
            callTree.put(funcName, new ArrayList<>());
        }

        CallInfo callInfo = new CallInfo();
        callInfo.level = currentDepth;
        callInfo.args = new ArrayList<>(args);
        callInfo.timestamp = callTree.get(funcName).size();
        callTree.get(funcName).add(callInfo);

        return currentDepth;
    }

    public void endCall(String funcName, Object returnValue) {
        if (currentCalls.containsKey(funcName) && currentCalls.get(funcName) > 0) {
            currentCalls.put(funcName, currentCalls.get(funcName) - 1);

            if (callTree.containsKey(funcName) && !callTree.get(funcName).isEmpty()) {
                List<CallInfo> calls = callTree.get(funcName);
                calls.get(calls.size() - 1).returnValue = returnValue;
            }
        }
    }

    public Object getBaseCaseValue(String funcName, List<Object> args) {
        if (funcName.equals("factorial") && !args.isEmpty()) {
            int n = (int) args.get(0);
            return n <= 1 ? 1 : n;
        } else if (funcName.equals("fibonacci") && !args.isEmpty()) {
            int n = (int) args.get(0);
            return n <= 1 ? n : 1;
        } else if (funcName.equals("gcd") && args.size() >= 2) {
            int b = (int) args.get(1);
            return b == 0 ? args.get(0) : 1;
        } else if (funcName.equals("power") && args.size() >= 2) {
            int exp = (int) args.get(1);
            return exp == 0 ? 1 : args.get(0);
        }
        return null;
    }

    public void reset() {
        callTree.clear();
        currentCalls.clear();
    }

    public Map<String, List<CallInfo>> getCallTree() {
        return callTree;
    }

    public static class CallInfo {
        public int level;
        public List<Object> args;
        public Object returnValue;
        public int timestamp;
        public List<String> steps;

        public CallInfo() {
            this.steps = new ArrayList<>();
        }
    }
}{
}
