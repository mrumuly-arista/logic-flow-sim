# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

import sys
import math
from sim import Topology, Node as SimNode, Link as SimLink
from PyQt5.QtCore import Qt, pyqtSignal, QObject
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
    QTextEdit,
)

class ToolTipWindow(QMainWindow):
    """
    Every node and link when clicked will create a popup where the state can be viewed and edited.
    It now displays actual node state.
    """
    # Define a signal to emit when the item should be deleted
    delete_item_from_scene = pyqtSignal(object)

    def __init__(self, parent, node_name="Detail Window", node_state=None):
        super().__init__()
        self.parent_item = parent
        self.node_name = node_name
        self.node_state = node_state if node_state is not None else {}

        self.setWindowTitle(f"Details for {self.node_name}")
        self.setGeometry(200, 200, 400, 300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.name_label = QLabel(f"Node: {self.node_name}")
        layout.addWidget(self.name_label)

        self.state_display = QTextEdit()
        self.state_display.setReadOnly(True)
        self._update_state_display()
        layout.addWidget(self.state_display)

        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._on_delete_click)
        layout.addWidget(remove_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def _update_state_display(self):
        state_text = ""
        for key, value in self.node_state.items():
            state_text += f"{key}: {value}\n"
        self.state_display.setText(state_text)

    def update_node_state_display(self, new_state):
        self.node_state = new_state
        self._update_state_display()

    def _on_delete_click(self):
        if self.parent_item:
            self.delete_item_from_scene.emit(self.parent_item)
            self.close()

class UILink(QGraphicsItem):
    """
    Each link will be a line. Hopefully a bold enough line to be easily clickable but well see
    """

class UINode(QGraphicsEllipseItem):
    """
    Each switch/agent will be represented as a node here.
    It holds a reference to its corresponding simulation node.
    """
    def __init__(self, parent, sim_node_name="default0", x=0, y=0, size = 100):
        super().__init__(-size/2, -size/2, size/2, size/2)
        self.name = sim_node_name
        self.parent = parent
        self._sim_node_ref = None
        self.detail_window = None

        fill_color = Qt.gray
        outline_color = Qt.black

        pen = QPen(outline_color)
        pen.setWidth(1)
        self.setBrush(QBrush(fill_color))
        self.setPen(pen)
        self.setPos(x,y)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self.text_item = QGraphicsTextItem(self.name, self)
        self._center_text()
    
    def set_sim_node_ref(self, sim_ref):
        self._sim_node_ref = sim_ref

    def update_ui_from_sim_state(self):
        """Updates the UI node's visual representation based on its sim node's state."""
        if self._sim_node_ref:
            state = self._sim_node_ref.state
            # if state.waiting:
            #     self.setBrush(QBrush(Qt.green))
            # else:
            #     self.setBrush(QBrush(Qt.red))

            if self.detail_window and self.detail_window.isVisible():
                self.detail_window.update_node_state_display(state)

    def _center_text(self):
        text_rect = self.text_item.boundingRect()
        ellipse_rect = self.boundingRect()
        x_pos = ellipse_rect.center().x() - text_rect.width() / 2
        y_pos = ellipse_rect.center().y() - text_rect.height() / 2
        self.text_item.setPos(x_pos, y_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._sim_node_ref:
                self.detail_window = ToolTipWindow(self, self.name, self._sim_node_ref.state)
                print(self.scene().parent)
                self.detail_window.delete_item_from_scene.connect(self.parent.remove_ui_node)
                self.detail_window.show()
            else:
                print(f"Warning: UINode {self.name} has no associated SimNode.")
        super().mousePressEvent(event)

class MainWindow(QWidget):
    """
    Main setup for GUI. View part of MVC design
    """
    def __init__(self, controller_ref):
        super().__init__()
        self._controller = controller_ref # Reference to the main controller

        # Config
        self.scene = QGraphicsScene(0, 0, 500, 500)
        self.ui_nodes = {} # Dictionary to map sim_node_name to UINode object

        self.setWindowTitle("Simulation GUI")
        self.setGeometry(100, 100, 1000, 700) # Increased window size

        # Output Log for Controller messages
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)

        # MENU CONTROL WIDGETS
        vbox_controls = QVBoxLayout()

        addNode_button = QPushButton("Add Sim Node")
        addNode_button.clicked.connect(self._add_sim_node_from_gui)
        vbox_controls.addWidget(addNode_button)

        step_button = QPushButton("Step")
        step_button.clicked.connect(self._controller.step_simulation)
        vbox_controls.addWidget(step_button)

        start_button = QPushButton("Continue")
        start_button.clicked.connect(self._controller.continue_simulation)
        vbox_controls.addWidget(start_button)

        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self._controller.reset)
        vbox_controls.addWidget(reset_button)

        vbox_controls.addWidget(self.output_log)

        view = QGraphicsView(self.scene)
        view.setRenderHint(QPainter.Antialiasing)

        hbox = QHBoxLayout(self)
        hbox.addLayout(vbox_controls)
        hbox.addWidget(view)

        self.setLayout(hbox)
    
    def restart(self):
        while self.ui_nodes.values():
            self.remove_ui_node(self.ui_nodes.popitem()[1])
        self.output_log.clear()

    def _add_sim_node_from_gui(self):
        node_name = f"agent{len(self.ui_nodes)}"
        self._controller.add_sim_node(node_name)

    def add_ui_node(self, sim_node_name, sim_node_obj):
        """
        Creates and adds a UINode to the scene, linking it to the sim.Node object.
        Called by the Controller when a new sim node is created.
        """
        new_ui_node = UINode(self, sim_node_name)
        new_ui_node.set_sim_node_ref(sim_node_obj) # Link to the simulation node
        self.ui_nodes[sim_node_name] = new_ui_node
        self.scene.addItem(new_ui_node)
        self._align_ui_nodes()

    def update_ui_nodes(self):
        """
        aligns ui nodes to sim nodes
        """
        for ui_node in self.ui_nodes.values():
            ui_node.update_ui_from_sim_state()
        self.scene.update()

    def remove_ui_node(self, ui_node_item: UINode):
        """
        chop the ui and sim nodes
        """
        if ui_node_item and ui_node_item.scene() == self.scene:
            self.scene.removeItem(ui_node_item)
            if ui_node_item.name in self.ui_nodes:
                del self.ui_nodes[ui_node_item.name]
                self._controller.remove_sim_node(ui_node_item.name)
            self._align_ui_nodes()
            print(f"Removed UI item and requested removal of sim node: {ui_node_item.name}")

    def _align_ui_nodes(self):
        # aligns all the nodes into a circle
        midx = 250
        midy = 250
        radius = 200
        nodes_list = list(self.ui_nodes.values())
        if not nodes_list:
            return

        for i in range(len(nodes_list)):
            degree = i * 2 * math.pi / len(nodes_list)
            x = radius * math.sin(degree) + midx
            y = radius * math.cos(degree) + midy
            nodes_list[i].setPos(x, y)

    def log_message(self, message):
        self.output_log.append(message)


class Controller(QObject):
    """
    Communicates user input to stimulate model, then sends output to MainWindow for display
    Controller part of MVC
    """
    log_message_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.topology = Topology()
        self.simulation_loop = None

        self.main_window = MainWindow(self)
        self.log_message_signal.connect(self.main_window.log_message)

        self._initialize_simulation()

    def _initialize_simulation(self):
        self.log_message("Initializing example topology...")
        
        self.add_sim_node("c")
        self.add_sim_node("a")
        self.add_sim_node("b")

        self.simulation_loop = self.topology.step()
        self.log_message("Topo initialized.")

    def reset(self):
        self.main_window.restart()
        self.log_message("Resetting")
        self.topology = Topology()
        self.simulation_loop = None
        self._initialize_simulation()

    def add_sim_node(self, name, behavior="print(self.name)"):
        if name in self.topology.nodes:
            self.log_message(f"Node '{name}' already exists.")
            return
        behavior='\n'.join( [
        'print(self.name)',
        'self.state["power"] = True'
        'remaining = True',
    ] )

        sim_node = self.topology.addNode(name, behavior=behavior)
        self.main_window.add_ui_node(name, sim_node)
        self.log_message(f"Added sim node '{name}'.")

    def remove_sim_node(self, name):
        if name in self.topology.nodes:
            del self.topology.nodes[name]
            self.log_message(f"Removed sim node '{name}'.")
        else:
            self.log_message(f"Sim node '{name}' not found.")

    def step_simulation(self):
        try:
            # step once
            next(self.simulation_loop)
            self.log_message("\n--- Simulation Step ---")

            # update all of the nodes/links
            for node_name, sim_node_obj in self.topology.nodes.items():
                remaining_activities = node_name in self.topology.waiting
                self.log_message(f"Node: {sim_node_obj.name}, State: {sim_node_obj.state}, Is waiting: {remaining_activities}")

            self.main_window.update_ui_nodes()

        except StopIteration:
            self.log_message("Nothing to do")
        except Exception as e:
            self.log_message(f"Error during simulation step: {e}")

    def continue_simulation(self):
        self.log_message(f"continuing...\n")
        for _ in self.simulation_loop:
            pass
        self.log_message(f"converged")

    def log_message(self, message):
        self.log_message_signal.emit(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    controller = Controller()
    controller.main_window.show()

    sys.exit(app.exec_())
