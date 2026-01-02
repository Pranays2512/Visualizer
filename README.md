# Java Code Visualizer

A powerful Java code visualization system with step-by-step execution tracking, recursion visualization, and beautiful UI.


## 🚀 Setup Instructions

### Backend Setup (Java Spring Boot)

**Prerequisites:**
- Java 17 or higher
- Maven 3.6+

**Steps:**

1. **Navigate to backend directory:**
```bash
cd backend
```

2. **Install dependencies:**
```bash
mvn clean install
```

3. **Run the Spring Boot application:**
```bash
mvn spring-boot:run
```

The backend will start on `http://localhost:8080`

**Alternative - Run as JAR:**
```bash
mvn clean package
java -jar target/java-visualizer-1.0.0.jar
```

### Frontend Setup (HTML/CSS/JS)

**Prerequisites:**
- Any modern web browser
- A local web server (optional but recommended)

**Option 1: Using Python HTTP Server**
```bash
cd frontend
python -m http.server 3000
```
Then open `http://localhost:3000`

**Option 2: Using Node.js http-server**
```bash
npm install -g http-server
cd frontend
http-server -p 3000
```

**Option 3: Using VS Code Live Server**
- Install "Live Server" extension in VS Code
- Right-click on `index.html` → "Open with Live Server"

**Option 4: Direct File Access**
- Simply open `frontend/index.html` in your browser
- Note: Some features might not work due to CORS restrictions

## 📝 Configuration

### Backend Configuration

Edit `backend/src/main/resources/application.properties`:

```properties
# Server port
server.port=8080

# Enable CORS
spring.web.cors.allowed-origins=*

# Logging
logging.level.com.frosted.visualizer=DEBUG
```

### Frontend Configuration

Edit `frontend/visualizer.js` to change API endpoint:

```javascript
const API_BASE = 'http://localhost:8080/api';
```

## 🎮 Usage

1. **Start the backend server** (must be running on port 8080)

2. **Open the frontend** in your browser

3. **Write Java code** in the editor (or use the default example)

4. **Click "Run & Visualize"** to execute and visualize

5. **Use arrow buttons** or keyboard arrows to step through execution

## ✨ Features

### Visualization Capabilities
-  Variable tracking and updates
-  Array visualization with indices
-  Recursion tracking with call tree
-  Call stack visualization
-  Step-by-step execution
-  If/else branch visualization
-  Loop iteration tracking
-  Method call visualization
-  Return value tracking

### Supported Java Features
- Variables (int, String, boolean, etc.)
- Arrays and array operations
- Loops (for, while)
- Conditionals (if/else)
- Methods and recursion
- Binary operations
- Method calls
- Return statements

### UI Features
- 🎨 Beautiful frosted glass design
- 🌙 Dark/Light theme toggle
- ⌨️ Keyboard shortcuts (Ctrl+Enter to run, arrows to navigate)
- 📱 Responsive design
- ✨ Smooth animations
- 🎯 Real-time step info display

## 🔧 Development

### Adding New Features

**Backend - Add new widget type:**

1. Update `VisualizationStep.VariableState` to include new widget metadata
2. Modify `CodeVisualizer.determineWidgetType()` to detect your type
3. Update frontend `createWidget()` to render the new type

**Frontend - Add new visualization:**

1. Create rendering function in `visualizer.js`
2. Add CSS styling in `styles.css`
3. Update `createWidget()` to use new renderer

### Testing

**Backend Tests:**
```bash
cd backend
mvn test
```

**Manual Testing:**
Test with these example codes:

**Simple Variables:**
```java
public class Test {
    public static void main(String[] args) {
        int x = 5;
        int y = 10;
        int sum = x + y;
    }
}
```

**Recursion:**
```java
public class Test {
    public static int factorial(int n) {
        if (n <= 1) return 1;
        return n * factorial(n - 1);
    }
    
    public static void main(String[] args) {
        int result = factorial(5);
    }
}
```

**Arrays:**
```java
public class Test {
    public static void main(String[] args) {
        int[] arr = {1, 2, 3, 4, 5};
        for (int i = 0; i < arr.length; i++) {
            arr[i] = arr[i] * 2;
        }
    }
}
```

## 🐛 Troubleshooting

### Backend Issues

**Port already in use:**
```bash
# Change port in application.properties or kill process
lsof -ti:8080 | xargs kill -9
```

**JavaParser errors:**
- Ensure Java code is syntactically correct
- Check for unsupported language features

### Frontend Issues

**CORS errors:**
- Ensure backend CORS is properly configured
- Use a proper web server instead of file:// protocol

**API connection failed:**
- Verify backend is running on port 8080
- Check browser console for errors
- Ensure API_BASE URL is correct

**Visualization not updating:**
- Check browser console for JavaScript errors
- Verify API response format matches expected structure

## 📦 Building for Production

### Backend JAR
```bash
cd backend
mvn clean package
# JAR will be in target/java-visualizer-1.0.0.jar
```

### Frontend Optimization
```bash
# Minify JavaScript
npx terser visualizer.js -o visualizer.min.js

# Minify CSS
npx csso styles.css -o styles.min.css
```

---

**Happy Visualizing! 🎉**