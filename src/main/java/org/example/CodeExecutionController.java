package org.example;

import org.springframework.web.bind.annotation.*;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.*;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
public class CodeExecutionController {

    private static final ObjectMapper objectMapper = new ObjectMapper();

    @PostMapping("/execute")
    public ExecutionResult executeCode(@RequestBody ExecutionRequest request) {
        ExecutionResult result = new ExecutionResult();

        try {
            String code = request.getCode();
            String input = request.getInput();

            // Parse and analyze the code
            CodeAnalyzer analyzer = new CodeAnalyzer(code, input);
            List<VisualizationStep> steps = analyzer.analyze();

            result.setSteps(steps);
            result.setOutput(analyzer.getOutput());
            result.setSuccess(true);

        } catch (Exception e) {
            result.setSuccess(false);
            result.setOutput("Error: " + e.getMessage());
            result.setSteps(new ArrayList<>());
        }

        return result;
    }

    // Inner Classes
    public static class ExecutionRequest {
        private String code;
        private String input;

        public String getCode() { return code; }
        public void setCode(String code) { this.code = code; }
        public String getInput() { return input; }
        public void setInput(String input) { this.input = input; }
    }

    public static class ExecutionResult {
        private String output;
        private List<VisualizationStep> steps;
        private boolean success;

        public String getOutput() { return output; }
        public void setOutput(String output) { this.output = output; }
        public List<VisualizationStep> getSteps() { return steps; }
        public void setSteps(List<VisualizationStep> steps) { this.steps = steps; }
        public boolean isSuccess() { return success; }
        public void setSuccess(boolean success) { this.success = success; }
    }

    public static class VisualizationStep {
        private int line;
        private String description;
        private Map<String, VariableState> variables;
        private String callStack;
        private String highlight;

        public VisualizationStep(int line, String description, Map<String, VariableState> variables) {
            this.line = line;
            this.description = description;
            this.variables = variables != null ? variables : new HashMap<>();
            this.callStack = "";
            this.highlight = "";
        }

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
    }

    public static class VariableState {
        private String type;
        private String value;
        private Map<String, Object> metadata;

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
    }
}