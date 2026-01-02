package com.frosted.visualizer.controller;

import com.frosted.visualizer.model.VisualizationStep;
import com.frosted.visualizer.service.CodeVisualizer;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * REST API controller for code visualization
 */
@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
public class VisualizerController {

    @PostMapping("/execute")
    public ExecutionResult executeCode(@RequestBody ExecutionRequest request) {
        ExecutionResult result = new ExecutionResult();

        try {
            String code = request.getCode();
            String input = request.getInput();

            // Create visualizer and analyze code
            CodeVisualizer visualizer = new CodeVisualizer(code, input);
            List<VisualizationStep> steps = visualizer.analyze();

            result.setSteps(steps);
            result.setOutput(visualizer.getOutput());
            result.setSuccess(true);

        } catch (Exception e) {
            result.setSuccess(false);
            result.setOutput("Error: " + e.getMessage());
            result.setSteps(new ArrayList<>());
            e.printStackTrace();
        }

        return result;
    }

    // Request/Response classes
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
}