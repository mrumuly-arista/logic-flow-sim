# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

import sys
import math

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QBrush, QPainter, QPen, QColor, QPainterPath, QPainterPathStroker
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

from sim import Topology, Node as SimNode, Link as SimLink # Assuming 'sim' is a custom module

# --- Constants ---
NODE_SIZE = 100
LINK_THICKNESS_NORMAL = 5
LINK_THICKNESS_HIGHLIGHT = 10
LINK_COLOR_NORMAL = QColor(100, 0, 0)
LINK_COLOR_HIGHLIGHT = QColor(100, 10, 0)
NODE_FILL_COLOR = Qt.gray
NODE_OUTLINE_COLOR = Qt.black
NODE_OUTLINE_WIDTH = 1
SCENE_WIDTH = 500
SCENE_HEIGHT = 500
MAIN_WINDOW_X = 100
MAIN_WINDOW_Y = 100
MAIN_WINDOW_WIDTH = 1000
MAIN_WINDOW_HEIGHT = 700
TOOLTIP_WINDOW_X = 200
TOOLTIP_WINDOW_Y = 200
TOOLTIP_WINDOW_WIDTH = 400
TOOLTIP_WINDOW_HEIGHT = 300
ALIGNMENT_RADIUS = 200

class ToolTipWindow(QMainWindow):
    """
    A pop-up window to display and interact with the state of a simulation item (node or link).
    Allows viewing the item's state and triggering its removal from the simulation.
    """
    delete_item_from_scene = pyqtSignal(object)

    def __init__(self, parent_item: QGraphicsItem, item_name: str, item_state: dict = None):
        """
        Initializes the ToolTipWindow.

        Args:
            parent_item: The QGraphicsItem (UINode or UILink) this window is associated with.
            item_name: The name of the simulation item (e.g., node name, link name).
            item_state: The current state dictionary of the simulation item.
        """
        super().__init__()
        self._parent_item = parent_item
        self._item_name = item_name
        self._item_state = item_state if item_state is not None else {}

        self._setup_ui()
        self._update_state_display()

    def _setup_ui(self):
        """Configures the window's user interface elements."""
        self.setWindowTitle(f"Details for {self._item_name}")
        self.setGeometry(TOOLTIP_WINDOW_X, TOOLTIP_WINDOW_Y, TOOLTIP_WINDOW_WIDTH, TOOLTIP_WINDOW_HEIGHT)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.name_label = QLabel(f"Item: {self._item_name}")
        layout.addWidget(self.name_label)

        self.state_display = QTextEdit()
        self.state_display.setReadOnly(True)
        layout.addWidget(self.state_display)

        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._on_delete_clicked)
        layout.addWidget(remove_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

    def _update_state_display(self):
        """Populates the state display QTextEdit with the current item state."""
        state_text = "\n".join(f"{key}: {value}" for key, value in self._item_state.items())
        self.state_display.setText(state_text)

    def update_item_state_display(self, new_state: dict):
        """
        Updates the displayed state of the item.

        Args:
            new_state: The new state dictionary for the item.
        """
        self._item_state = new_state
        self._update_state_display()

    def _on_delete_clicked(self):
        """Handles the 'Remove' button click, emitting a signal to delete the item."""
        if self._parent_item:
            self.delete_item_from_scene.emit(self._parent_item)
            self.close()

class UILink(QGraphicsLineItem):
    """
    Represents a link in the UI, connecting two UINode objects.
    Visualized as a line, with click interactions to view details.
    """
    def __init__(self, parent_window: 'MainWindow', name: str, start_node: 'UINode', end_node: 'UINode'):
        """
        Initializes a UILink.

        Args:
            parent_window: The main window reference.
            name: The name of the link.
            start_node: The UINode representing the starting point of the link.
            end_node: The UINode representing the ending point of the link.
        """
        super().__init__()
        self.name = name
        self._parent_window = parent_window
        self.start_node = start_node
        self.end_node = end_node
        self._sim_link_ref: SimLink = None
        self._detail_window: ToolTipWindow = None

        self._setup_appearance()

        # Register this link with its connected nodes
        self.start_node.connected_lines.append(self)
        self.end_node.connected_lines.append(self)
        
        self.update_position() # Set initial position

    def _setup_appearance(self):
        """Configures the visual appearance of the link."""
        self.setPen(QPen(LINK_COLOR_NORMAL, LINK_THICKNESS_NORMAL, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setZValue(-1) # Draw links behind nodes

    def set_sim_link_ref(self, link_ref: SimLink):
        """
        Sets the reference to the corresponding simulation link object.
        """
        self._sim_link_ref = link_ref

    def update_position(self):
        """Updates the line's start and end points based on the connected nodes' positions."""
        if self.start_node and self.end_node:
            self.setLine(self.start_node.center_point().x(), self.start_node.center_point().y(),
                         self.end_node.center_point().x(), self.end_node.center_point().y())

    def mousePressEvent(self, event):
        """Handles mouse press events on the link."""
        print(f"Link chosen between {self.start_node.name} and {self.end_node.name}")
        self.setPen(QPen(LINK_COLOR_HIGHLIGHT, LINK_THICKNESS_HIGHLIGHT, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.update()

        # Open detail window for the link
        if self._sim_link_ref:
            self._detail_window = ToolTipWindow(self, self.name, self._sim_link_ref.state)
            self._detail_window.delete_item_from_scene.connect(self._parent_window.remove_ui_link)
            self._detail_window.show()
        else:
            print(f"Warning: UILink {self.name} has no associated SimLink.")

        super().mousePressEvent(event)

class UINode(QGraphicsEllipseItem):
    """
    Represents a simulation node (e.g., switch/agent) in the UI.
    It visualizes the node as an ellipse and holds a reference to its corresponding simulation node.
    Clicking the node opens a detail window.
    """
    def __init__(self, parent_window: 'MainWindow', sim_node_name: str = "default0", x: float = 0, y: float = 0):
        """
        Initializes a UINode.

        Args:
            parent_window: The main window reference.
            sim_node_name: The name of the simulation node.
            x: Initial X coordinate.
            y: Initial Y coordinate.
        """
        super().__init__(-NODE_SIZE / 2, -NODE_SIZE / 2, NODE_SIZE, NODE_SIZE)
        self.name = sim_node_name
        self._parent_window = parent_window
        self._sim_node_ref: SimNode = None
        self._detail_window: ToolTipWindow = None
        self.connected_lines: list[UILink] = [] # Store references to connected UILinks

        self._setup_appearance(x, y)

    def _setup_appearance(self, x: float, y: float):
        """Configures the visual appearance and initial position of the node."""
        pen = QPen(NODE_OUTLINE_COLOR)
        pen.setWidth(NODE_OUTLINE_WIDTH)
        self.setBrush(QBrush(NODE_FILL_COLOR))
        self.setPen(pen)
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable) # Allows selection, but not dragging currently

        self.text_item = QGraphicsTextItem(self.name, self)
        self._center_text()

    def set_sim_node_ref(self, sim_ref: SimNode):
        """
        Sets the reference to the corresponding simulation node object.
        """
        self._sim_node_ref = sim_ref

    def center_point(self):
        """
        Calculates and returns the global scene coordinates of the node's center.
        """
        return self.scenePos() + self.boundingRect().center()

    def update_ui_from_sim_state(self):
        """Updates the UI node's visual representation and detail window based on its sim node's state."""
        if self._sim_node_ref:
            state = self._sim_node_ref.state
            # Example: Change color based on state (uncomment and adjust as needed)
            # if state.get("waiting", False):
            #     self.setBrush(QBrush(Qt.green))
            # else:
            #     self.setBrush(QBrush(Qt.red))

            if self._detail_window and self._detail_window.isVisible():
                self._detail_window.update_item_state_display(state)

    def _center_text(self):
        """Centers the text item within the ellipse."""
        text_rect = self.text_item.boundingRect()
        ellipse_rect = self.boundingRect()
        x_pos = ellipse_rect.center().x() - text_rect.width() / 2
        y_pos = ellipse_rect.center().y() - text_rect.height() / 2
        self.text_item.setPos(x_pos, y_pos)

    def mousePressEvent(self, event):
        """Handles mouse press events on the node."""
        if event.button() == Qt.LeftButton:
            if self._sim_node_ref:
                # Pass self as the parent item to the ToolTipWindow for deletion signal
                self._detail_window = ToolTipWindow(self, self.name, self._sim_node_ref.state)
                # Connect the signal from the ToolTipWindow to the MainWindow's removal method
                self._detail_window.delete_item_from_scene.connect(self._parent_window.remove_ui_node)
                self._detail_window.show()
            else:
                print(f"Warning: UINode {self.name} has no associated SimNode.")
        super().mousePressEvent(event)

class MainWindow(QWidget):
    """
    The main GUI window, responsible for displaying the simulation topology
    and providing controls for interacting with the simulation.
    It acts as the 'View' in the MVC pattern.
    """
    def __init__(self, controller_ref: 'Controller'):
        """
        Initializes the MainWindow.

        Args:
            controller_ref: A reference to the main Controller object.
        """
        super().__init__()
        self._controller = controller_ref # Reference to the main controller

        self.scene = QGraphicsScene(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.ui_nodes: dict[str, UINode] = {} # Map sim_node_name to UINode object
        self.ui_links: dict[str, UILink] = {} # Map sim_link_name to UILink object

        self._setup_ui()

    def _setup_ui(self):
        """Configures the main window's user interface."""
        self.setWindowTitle("Simulation GUI")
        self.setGeometry(MAIN_WINDOW_X, MAIN_WINDOW_Y, MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT)

        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)

        control_layout = self._create_control_panel()
        
        graphics_view = QGraphicsView(self.scene)
        graphics_view.setRenderHint(QPainter.Antialiasing)
        graphics_view.setMouseTracking(True)

        main_layout = QHBoxLayout(self)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(graphics_view)

        self.setLayout(main_layout)

    def _create_control_panel(self) -> QVBoxLayout:
        """Creates and returns the vertical layout for control buttons and log."""
        vbox_controls = QVBoxLayout()

        add_node_button = QPushButton("Add Sim Node")
        add_node_button.clicked.connect(self._on_add_sim_node_clicked)
        vbox_controls.addWidget(add_node_button)

        step_button = QPushButton("Step Simulation")
        step_button.clicked.connect(self._controller.step_simulation)
        vbox_controls.addWidget(step_button)

        continue_button = QPushButton("Continue Simulation")
        continue_button.clicked.connect(self._controller.continue_simulation)
        vbox_controls.addWidget(continue_button)

        reset_button = QPushButton("Reset Simulation")
        reset_button.clicked.connect(self._controller.reset_simulation)
        vbox_controls.addWidget(reset_button)

        vbox_controls.addWidget(self.output_log)
        return vbox_controls
    
    def restart_ui(self):
        """Clears all UI nodes and links and resets the output log."""
        # Iterate over a copy of the values to avoid modifying the dictionary during iteration
        for ui_node_item in list(self.ui_nodes.values()):
            self.remove_ui_node(ui_node_item)
        self.ui_nodes.clear() # Ensure the dictionary is empty
        self.ui_links.clear()
        self.output_log.clear()

    def _on_add_sim_node_clicked(self):
        """Handles the 'Add Sim Node' button click."""
        node_name = f"agent{len(self.ui_nodes)}"
        self._controller.add_sim_node(node_name)

    def add_ui_node(self, sim_node_name: str, sim_node_obj: SimNode):
        """
        Adds a new UINode to the scene and internal tracking.

        Args:
            sim_node_name: The name of the simulation node.
            sim_node_obj: The corresponding SimNode object.
        """
        new_ui_node = UINode(self, sim_node_name)
        new_ui_node.set_sim_node_ref(sim_node_obj)

        self.ui_nodes[sim_node_name] = new_ui_node
        self.scene.addItem(new_ui_node)
        self._align_ui_elements()

    def update_ui_nodes(self):
        """Updates the visual state of all UI nodes based on their simulation state."""
        for ui_node in self.ui_nodes.values():
            ui_node.update_ui_from_sim_state()
        self.scene.update()

    def remove_ui_node(self, ui_node_item: UINode):
        """
        Removes a UINode from the scene and triggers its removal from the simulation.

        Args:
            ui_node_item: The UINode object to remove.
        """
        if ui_node_item and ui_node_item.scene() == self.scene:
            # Create a copy of connected_lines as it might be modified during iteration
            for link in list(ui_node_item.connected_lines):
                self.remove_ui_link(link)

            self.scene.removeItem(ui_node_item)
            if ui_node_item.name in self.ui_nodes:
                del self.ui_nodes[ui_node_item.name]
                self._controller.remove_sim_node(ui_node_item.name) # Inform controller to remove sim node
            self._align_ui_elements()
            print(f"Removed UI node and requested removal of sim node: {ui_node_item.name}")
    
    def add_ui_link(self, sim_link_name: str, sim_link_obj: SimLink, peer1_name: str, peer2_name: str):
        """
        Adds a new UILink to the scene and internal tracking.

        Args:
            sim_link_name: The name of the simulation link.
            sim_link_obj: The corresponding SimLink object.
            peer1_name: The name of the first connected node.
            peer2_name: The name of the second connected node.
        """
        peer1_node = self.ui_nodes.get(peer1_name)
        peer2_node = self.ui_nodes.get(peer2_name)

        if not peer1_node or not peer2_node:
            self._controller.log_message(f"Cannot add link '{sim_link_name}': one or both nodes '{peer1_name}', '{peer2_name}' do not exist in UI.")
            return

        new_ui_link = UILink(self, sim_link_name, peer1_node, peer2_node)
        new_ui_link.set_sim_link_ref(sim_link_obj)

        self.ui_links[sim_link_name] = new_ui_link
        self.scene.addItem(new_ui_link)
        self._align_ui_elements()

    def update_ui_links(self):
        """Updates the positions of all UI links based on their connected nodes."""
        for ui_link in self.ui_links.values():
            ui_link.update_position()
        self.scene.update()

    def remove_ui_link(self, ui_link_item: UILink):
        """
        Removes a UILink from the scene and triggers its removal from the simulation.

        Args:
            ui_link_item: The UILink object to remove.
        """
        if ui_link_item and ui_link_item.scene() == self.scene:
            # Remove link from connected nodes' lists
            if ui_link_item.start_node and ui_link_item in ui_link_item.start_node.connected_lines:
                ui_link_item.start_node.connected_lines.remove(ui_link_item)
            if ui_link_item.end_node and ui_link_item in ui_link_item.end_node.connected_lines:
                ui_link_item.end_node.connected_lines.remove(ui_link_item)

            self.scene.removeItem(ui_link_item)
            if ui_link_item.name in self.ui_links:
                del self.ui_links[ui_link_item.name]
                self._controller.remove_sim_link(ui_link_item.name) # Inform controller to remove sim link
            print(f"Removed UI link and requested removal of sim link: {ui_link_item.name}")

    def _align_ui_elements(self):
        """
        Aligns all UI nodes in a circular formation and updates the positions of all links.
        """
        mid_x = SCENE_WIDTH / 2
        mid_y = SCENE_HEIGHT / 2
        
        nodes_list = list(self.ui_nodes.values())
        num_nodes = len(nodes_list)

        if not nodes_list:
            return

        for i, node in enumerate(nodes_list):
            angle = i * 2 * math.pi / num_nodes
            x = ALIGNMENT_RADIUS * math.sin(angle) + mid_x
            y = ALIGNMENT_RADIUS * math.cos(angle) + mid_y
            node.setPos(x, y)
        self.update_ui_links()

    def log_message(self, message: str):
        """Appends a message to the output log display."""
        self.output_log.append(message)

class Controller(QObject):
    """
    Manages the simulation logic and acts as the bridge between the UI (MainWindow)
    and the simulation model (Topology). It handles user input and updates the UI
    based on simulation events. This is the 'Controller' part of the MVC pattern.
    """
    log_message_signal = pyqtSignal(str)

    def __init__(self):
        """Initializes the Controller, setting up the simulation and UI."""
        super().__init__()
        self._topology = Topology()
        self._simulation_generator = None # Generator for stepping through simulation

        self.main_window = MainWindow(self)
        # Connect controller's log signal to main window's log method
        self.log_message_signal.connect(self.main_window.log_message)

        self._initialize_simulation_example()

    def _initialize_simulation_example(self):
        """Sets up an initial example simulation topology with nodes and links."""
        self.log_message("Initializing example topology...")
        
        # Define a simple behavior for simulation nodes
        node_behavior = '\n'.join( [
            'if not self.state[ "initialized" ]:',
            '   self.send( next( iter( self.txIntfs ) ), "hello wolrd" )',
            '   self.state[ "initialized" ] = True',
            'elif self.rxWaiting:',
            '   print( f"{self.name} got {self.recv()}" )',
            'self.remaining = bool( self.rxWaiting or not self.state[ "initialized" ] )',
        ] )
        
        self.add_sim_node("a", behavior=node_behavior, state={'initialized': False})
        self.add_sim_node("b", behavior=node_behavior, state={'initialized': False})
        self.add_sim_link("link1", "a", "b")

        self._simulation_generator = self._topology.step()
        self.log_message("Topology initialized.")

    def reset_simulation(self):
        """Resets the entire simulation, clearing UI and re-initializing topology."""
        self.log_message("Resetting simulation...")
        self.main_window.restart_ui()
        self._topology = Topology()
        self._simulation_generator = None
        self._initialize_simulation_example()
        self.log_message("Simulation reset complete.")

    def add_sim_node(self, name: str, behavior: str = "print(self.name)", state: dict = None):
        """
        Adds a new simulation node to the topology and its corresponding UI representation.

        Args:
            name: The unique name for the new node.
            behavior: The Python code string defining the node's simulation behavior.
            state: An initial state dictionary for the node.
        """
        if name in self._topology.nodes:
            self.log_message(f"Node '{name}' already exists in simulation.")
            return 
        
        sim_node = self._topology.addNode(name, behavior=behavior, state=state if state is not None else {})
        self.main_window.add_ui_node(name, sim_node)
        self.log_message(f"Added simulation node '{name}'.")

    def remove_sim_node(self, name: str):
        """
        Removes a simulation node from the topology.

        Args:
            name: The name of the node to remove.
        """
        if name in self._topology.nodes:
            del self._topology.nodes[name]
            self.log_message(f"Removed simulation node '{name}'.")
        else:
            self.log_message(f"Simulation node '{name}' not found.")

    def add_sim_link(self, name: str, peer1_name: str, peer2_name: str):
        """
        Adds a new simulation link between two existing nodes to the topology and its UI representation.

        Args:
            name: The unique name for the new link.
            peer1_name: The name of the first node to connect.
            peer2_name: The name of the second node to connect.
        """
        if name in self._topology.links:
            self.log_message(f"Link '{name}' already exists in simulation.")
            return

        try:
            sim_link = self._topology.addLink(peer1_name, peer2_name)
            self.main_window.add_ui_link(name, sim_link, peer1_name, peer2_name)
            self.log_message(f"Added simulation link '{name}' between '{peer1_name}' and '{peer2_name}'.")
        except Exception as e:
            self.log_message(f"Failed to add link '{name}': {e}. Ensure nodes '{peer1_name}' and '{peer2_name}' exist.")


    def remove_sim_link(self, name: str):
        """
        Removes a simulation link from the topology.

        Args:
            name: The name of the link to remove.
        """
        if name in self._topology.links:
            del self._topology.links[name]
            self.log_message(f"Removed simulation link '{name}'.")
        else:
            self.log_message(f"Simulation link '{name}' not found.")

    def step_simulation(self):
        """
        Executes a single step of the simulation and updates the UI accordingly.
        """
        if not self._simulation_generator:
            self.log_message("Simulation not initialized. Please reset or add nodes.")
            return

        try:
            next(self._simulation_generator)
            self.log_message("\n--- Simulation Step Executed ---")

            # Log current state of simulation nodes and update UI
            for node_name, sim_node_obj in self._topology.nodes.items():
                is_waiting = node_name in self._topology.waiting
                self.log_message(f"Node: {sim_node_obj.name}, State: {sim_node_obj.state}, Is waiting: {is_waiting}")

            self.main_window.update_ui_nodes()
            self.main_window.update_ui_links()

        except StopIteration:
            self.log_message("Simulation converged: Nothing left to do.")
            self._simulation_generator = None # Indicate that simulation is finished
        except Exception as e:
            self.log_message(f"Error during simulation step: {e}")
            self._simulation_generator = None # Stop further steps on error

    def continue_simulation(self):
        """
        Runs the simulation until it converges.
        """
        if not self._simulation_generator:
            self.log_message("Simulation not initialized or already converged.")
            return

        self.log_message("\n--- Continuing ---")
        try:
            for _ in self._simulation_generator:
                # For now only logs, need to add an update here
                pass
            self.log_message("Simulation converged successfully.")
        except Exception as e:
            self.log_message(f"Error during continuous simulation: {e}")
        finally:
            self._simulation_generator = None # Mark as converged or errored
            self.main_window.update_ui_nodes()
            self.main_window.update_ui_links()


    def log_message(self, message: str):
        """
        Emits a signal to log a message to the UI's output log.

        Args:
            message: The string message to log.
        """
        self.log_message_signal.emit(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    controller = Controller()
    controller.main_window.show()

    sys.exit(app.exec_())
