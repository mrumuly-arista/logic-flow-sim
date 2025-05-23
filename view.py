# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

import sys
import math
from sim import Topology, Node as SimNode, Link as SimLink
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QBrush, QPainter, QPen
from PyQt5.QtGui import QColor, QPen, QBrush, QPainterPath, QPainterPathStroker
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
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

class UILink(QGraphicsLineItem):
    """
    Each link will be a line. Hopefully a bold enough line to be easily clickable but well see
    """
    def __init__(self, parent, name, start_node, end_node):
        super().__init__()
        self.name = name
        self.parent = parent
        self.start_node = start_node
        self.end_node = end_node
        self.sim_link_ref = None

        self.setPen(QPen(QColor(100, 0, 0), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setZValue(-1)

        self.start_node.connected_lines.append(self)
        self.end_node.connected_lines.append(self)
        
        self.updatePosition() # Set initial position
    
    def set_sim_link_ref(self, link_ref):
        self.sim_link_ref = link_ref

    def updatePosition(self):
        if self.start_node and self.end_node:
            self.setLine(self.start_node.center_point().x(), self.start_node.center_point().y(),
                         self.end_node.center_point().x(), self.end_node.center_point().y())

    def mousePressEvent(self, event):
        print(f"Link chosen between {self.start_node.name} and {self.end_node.name}")
        # You can emit a signal here or perform other actions
        self.setPen(QPen(QColor(100, 10, 0), 10, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.update()
        super().mousePressEvent(event)

class UINode(QGraphicsEllipseItem):
    """
    Each switch/agent will be represented as a node here.
    It holds a reference to its corresponding simulation node.
    """
    def __init__(self, parent, sim_node_name="default0", x=0, y=0, size = 100):
        super().__init__(-size/2, -size/2, size, size)
        self.name = sim_node_name
        self.parent = parent
        self._sim_node_ref = None
        self.detail_window = None
        self.connected_lines = []

        fill_color = Qt.gray
        outline_color = Qt.black

        pen = QPen(outline_color)
        pen.setWidth(1)
        self.setBrush(QBrush(fill_color))
        self.setPen(pen)
        self.setPos(x,y)
        # self.setFlag(QGraphicsItem.ItemIsMovable) # removed dragging for now
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self.text_item = QGraphicsTextItem(self.name, self)
        self._center_text()

    def set_sim_node_ref(self, sim_ref):
        self._sim_node_ref = sim_ref

    def center_point(self):
        return self.scenePos() + self.boundingRect().center()

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
        self.ui_links = {} # ditto

        self.setWindowTitle("Simulation GUI")
        self.setGeometry(100, 100, 1000, 700)

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
        view.setMouseTracking(True)

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
        new_ui_node = UINode(self, sim_node_name)
        new_ui_node.set_sim_node_ref(sim_node_obj) # Link to the simulation node

        self.ui_nodes[sim_node_name] = new_ui_node
        self.scene.addItem(new_ui_node)
        self._align_ui_nodes()

    def update_ui_nodes(self):
        for ui_node in self.ui_nodes.values():
            ui_node.update_ui_from_sim_state()
        self.scene.update()

    def remove_ui_node(self, ui_node_item: UINode):
        if ui_node_item and ui_node_item.scene() == self.scene:
            for link in list(ui_node_item.connected_lines): 
                self.remove_ui_link(link)

            self.scene.removeItem(ui_node_item)
            if ui_node_item.name in self.ui_nodes:
                del self.ui_nodes[ui_node_item.name]
                self._controller.remove_sim_node(ui_node_item.name)
            self._align_ui_nodes()
            print(f"Removed UI item and requested removal of sim node: {ui_node_item.name}")
    
    def add_ui_link(self, sim_link_name, sim_link_obj, peer1_name, peer2_name):
        if peer1_name not in self.ui_nodes or peer2_name not in self.ui_nodes:
            self._controller.log_message(f"Cannot add link '{sim_link_name}': one or both nodes '{peer1_name}', '{peer2_name}' do not exist.")
            return
        parent1 = self.ui_nodes[peer1_name]
        parent2 = self.ui_nodes[peer2_name]
        new_ui_link = UILink(self, sim_link_name, parent1, parent2)
        new_ui_link.set_sim_link_ref(sim_link_obj) # Link to the simulation node

        self.ui_links[sim_link_name] = new_ui_link
        self.scene.addItem(new_ui_link)
        self._align_ui_nodes()

    def update_ui_links(self):
        for ui_link in self.ui_links.values():
            ui_link.updatePosition()
        self.scene.update()

    def remove_ui_link(self, ui_link_item: UILink):
        if ui_link_item and ui_link_item.scene() == self.scene:
            if ui_link_item.start_node and ui_link_item in ui_link_item.start_node.connected_lines:
                ui_link_item.start_node.connected_lines.remove(ui_link_item)
            if ui_link_item.end_node and ui_link_item in ui_link_item.end_node.connected_lines:
                ui_link_item.end_node.connected_lines.remove(ui_link_item)

            self.scene.removeItem(ui_link_item)
            if ui_link_item.name in self.ui_links:
                del self.ui_links[ui_link_item.name]
                self._controller.remove_sim_link(ui_link_item.name)
            print(f"Removed UI item and requested removal of sim link: {ui_link_item.name}")


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
        self.update_ui_links()

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
        
        behavior = '\n'.join( [
            'if not self.state[ "initialized" ]:',
            '   self.send( next( iter( self.txIntfs ) ), "hello wolrd" )',
            '   self.state[ "initialized" ] = True',
            'elif self.rxWaiting:',
            '   print( f"{self.name} got {self.recv()}" )',
            'self.remaining = bool( self.rxWaiting or not self.state[ "initialized" ] )',
        ] )
        self.add_sim_node( "a", behavior=behavior, state={ 'initialized': False } )
        self.add_sim_node( "b", behavior=behavior, state={ 'initialized': False } )
        self.add_sim_link( "link1", "a", "b" )

        self.simulation_loop = self.topology.step()
        self.log_message("Topo initialized.")

    def reset(self):
        self.main_window.restart()
        self.log_message("Resetting")
        self.topology = Topology()
        self.simulation_loop = None
        self._initialize_simulation()

    def add_sim_node(self, name, behavior="print(self.name)", state = {}):
        if name in self.topology.nodes:
            self.log_message(f"Node '{name}' already exists.")
            return
        sim_node = self.topology.addNode(name, behavior=behavior, state=state)

        self.main_window.add_ui_node(name, sim_node)
        self.log_message(f"Added node '{name}'.")

    def remove_sim_node(self, name):
        if name in self.topology.nodes:
            del self.topology.nodes[name]
            self.log_message(f"Removed node '{name}'.")
        else:
            self.log_message(f"Node '{name}' not found.")

    def add_sim_link(self, name, peer1_name, peer2_name):
        if name in self.topology.links:
            self.log_message(f"Link '{name}' already exists.")
            return

        sim_link = self.topology.addLink(peer1_name, peer2_name)

        self.main_window.add_ui_link(name, sim_link, peer1_name, peer2_name)
        self.log_message(f"Added link '{name}'.")

    def remove_sim_link(self, name):
        if name in self.topology.links:
            del self.topology.links[name]
            self.log_message(f"Removed link '{name}'.")
        else:
            self.log_message(f"Link '{name}' not found.")

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
