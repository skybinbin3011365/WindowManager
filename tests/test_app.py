import sys
import os

print("Test app started")
print(f"Python version: {sys.version}")
print(f"Executable: {sys.executable}")
print(f"Working directory: {os.getcwd()}")

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
    print("PySide6 imported successfully")
    
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Test App")
    window.setGeometry(100, 100, 400, 300)
    
    label = QLabel("Test App Works!", window)
    label.move(50, 50)
    
    window.show()
    print("Window shown")
    
    sys.exit(app.exec())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)