import sys
import math

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsEllipseItem,
    QGraphicsTextItem,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QWidget,
)

class MyGraphicsScene(QGraphicsScene):
    delete_item_from_scene = pyqtSignal(QGraphicsEllipseItem)

    def __init__(self, parent=None):
        super().__init__(parent)

class ToolTipWindow(QMainWindow):
    """
    Every node and link when clicked will create a popup where the state can be viewed and edited
    """
    def __init__(self, parent, title="Detail Window", content_text="No details provided."):
        super().__init__()
        self.parent_item = parent
        self.setWindowTitle(title)
        self.setGeometry(200, 200, 400, 300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.label = QLabel(content_text)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._on_delete_click)
        layout.addWidget(remove_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def _on_delete_click(self):
        if self.parent_item:
            self.delete_item_from_scene.emit(self.parent_item)
            self.close()

class Node(QGraphicsEllipseItem):
    """
    Each switch/agent will be represented as a node here
    """
    def __init__(self, name="default0", x=0, y=0, size = 100):
        super().__init__(-size/2, -size/2, size/2, size/2)
        self.name = name
        self.state = {}
        fill_color = Qt.gray
        outline_color = Qt.black

        pen = QPen(outline_color)
        pen.setWidth(1)
        self.setBrush(QBrush(fill_color))
        self.setPen(pen)
        self.setPos(x,y)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        if type(self.name) == bool:
            self.name = "default"
        self.text_item = QGraphicsTextItem(self.name, self)
        self._center_text()

    def update_state(self, state):
        self.state = state

    def _center_text(self):
        text_rect = self.text_item.boundingRect()
        ellipse_rect = self.boundingRect()
        x_pos = ellipse_rect.center().x() - text_rect.width() / 2
        y_pos = ellipse_rect.center().y() - text_rect.height() / 2
        self.text_item.setPos(x_pos, y_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.detail_window = ToolTipWindow(self, self.name, "State filler")
            self.detail_window.show()
        super().mousePressEvent(event)


class MainWindow(QWidget):
    """
    Main render loop for GUI
    """
    def __init__(self):
        super().__init__()
        # config
        self.scene = QGraphicsScene(0, 0, 500, 500)
        self.nodes = []

        # create 10 example nodes
        num_agents = 10
        for i in range(num_agents):
            self.addNode( f"agent{i}"  )

        vbox = QVBoxLayout()
        addNode = QPushButton("Add Switch")
        addNode.clicked.connect(self.addNode)
        vbox.addWidget(addNode)

        view = QGraphicsView(self.scene)
        view.setRenderHint(QPainter.Antialiasing)

        hbox = QHBoxLayout(self)
        hbox.addLayout(vbox)
        hbox.addWidget(view)

        self.setLayout(hbox)

    
    def addNode(self, name = "default"):
        new_agent = Node( name )
        self.nodes.append(new_agent)
        self.scene.addItem(new_agent)
        
        self._alignNodes()

    def _alignNodes(self):
        # aligns all the nodes into a circle
        midx = 250
        midy = 250
        radius = 200
        for i in range(len(self.nodes)):
            degree = i * 2 * math.pi / len(self.nodes)
            x = radius * math.sin(degree) + midx
            y = radius * math.cos(degree) + midy
            self.nodes[i].setPos(x, y)

    def remove_item(self, item: QGraphicsEllipseItem):
        if item and item.scene() == self.scene: # Check if item is still in this scene
            self.scene.removeItem(item)
            print(f"Removed item: {item.name}")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    app.exec()