#!/usr/bin/env python3
"""
testPyQt.py - Test if PyQt5 is working
"""

import sys


def testPyQt():
    """Test PyQt5 installation"""
    print("Testing PyQt5 installation...")

    try:
        from PyQt5 import QtWidgets, QtCore
        print("✅ PyQt5 imported successfully")

        # Test creating application
        app = QtWidgets.QApplication(sys.argv)
        print("✅ QApplication created")

        # Test creating window
        window = QtWidgets.QMainWindow()
        window.setWindowTitle("PyQt Test")
        window.setGeometry(100, 100, 400, 300)

        # Add simple widget
        central = QtWidgets.QWidget()
        window.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout()
        central.setLayout(layout)

        label = QtWidgets.QLabel("PyQt5 is working!")
        label.setStyleSheet("font-size: 18px; padding: 20px;")
        layout.addWidget(label)

        button = QtWidgets.QPushButton("Close")
        button.clicked.connect(window.close)
        layout.addWidget(button)

        print("✅ Window created successfully")

        # Show window
        window.show()
        print("✅ Window displayed - you should see a test window")
        print("Close the window to continue...")

        app.exec_()
        print("✅ PyQt5 test completed successfully")
        return True

    except ImportError as e:
        print(f"❌ PyQt5 import failed: {e}")
        print("Try: pip install PyQt5")
        return False
    except Exception as e:
        print(f"❌ PyQt5 error: {e}")
        return False


def testPyQtGraph():
    """Test pyqtgraph"""
    print("\nTesting pyqtgraph...")

    try:
        import pyqtgraph as pg
        print("✅ pyqtgraph imported successfully")
        return True
    except ImportError as e:
        print(f"❌ pyqtgraph import failed: {e}")
        print("Try: pip install pyqtgraph")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("PyQt Installation Test")
    print("=" * 50)

    pyqt_ok = testPyQt()
    pyqtgraph_ok = testPyQtGraph()

    print("\n" + "=" * 50)
    print("Summary:")
    print(f"PyQt5: {'✅ Working' if pyqt_ok else '❌ Failed'}")
    print(f"pyqtgraph: {'✅ Working' if pyqtgraph_ok else '❌ Failed'}")

    if not pyqt_ok or not pyqtgraph_ok:
        print("\nTo fix, run:")
        print("pip install PyQt5 pyqtgraph")
        print("# or if that fails:")
        print("pip install --upgrade PyQt5 pyqtgraph")