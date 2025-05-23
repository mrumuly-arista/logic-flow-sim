# Copyright (c) 2025 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

import sys
import math
import os

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QBrush, QPainter, QPen, QColor, QPalette
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
    QGroupBox,
    QLineEdit,
    QComboBox,
)

from sim import Topology, Node as SimNode, Link as SimLink
from simFile import loadTopologyFile, dumpTopologyFile

# --- Constants ---
NODE_SIZE = 150
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
MAIN_WINDOW_WIDTH = 1500
MAIN_WINDOW_HEIGHT = 800
TOOLTIP_WINDOW_X = 200
TOOLTIP_WINDOW_Y = 200
TOOLTIP_WINDOW_WIDTH = 400
TOOLTIP_WINDOW_HEIGHT = 300
ALIGNMENT_RADIUS = 200

# Define some basic colors for the palette
COLOR_BACKGROUND_DARK = QColor(43, 43, 43) # Similar to original QSS
COLOR_TEXT_LIGHT = QColor(240, 240, 240)
COLOR_CONTROL_BACKGROUND = QColor(51, 51, 51) # For group boxes, etc.
COLOR_BORDER_GREY = QColor(68, 68, 68)

class QtOutputStream(QObject):
    text_written = pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass

    def isatty(self):
        return False

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
        state_text_parts = []
        for key, value in self._item_state.items():
            if isinstance(value, dict):
                state_text_parts.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, list) and len(sub_value) > 5: # Truncate long queues
                        sub_value_display = f"{sub_value[:5]}... (total {len(sub_value)})"
                    else:
                        sub_value_display = sub_value
                    state_text_parts.append(f"  {sub_key}: {sub_value_display}")
            else:
                state_text_parts.append(f"{key}: {value}")
        self.state_display.setText("\n".join(state_text_parts))

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
        self._sim_link_ref1: SimLink = None
        self._sim_link_ref2: SimLink = None
        self._detail_window: ToolTipWindow = None

        self.info_text_item = QGraphicsTextItem(self)
        info_font = self.info_text_item.font()
        info_font.setPointSize(max(6, info_font.pointSize() - 3))
        self.info_text_item.setFont(info_font)
        self.info_text_item.setDefaultTextColor(NODE_OUTLINE_COLOR)

        self._setup_appearance()

        # Register this link with its connected nodes
        self.start_node.connected_lines.append(self)
        self.end_node.connected_lines.append(self)
        
        self.update_position() # Set initial position

    def _setup_appearance(self):
        """Configures the visual appearance of the link."""
        self.setPen(QPen(LINK_COLOR_NORMAL, LINK_THICKNESS_NORMAL, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setZValue(-1) # Draw links behind nodes

    def set_sim_link_ref2(self, link_ref: SimLink ):
        """
        Sets the reference to the corresponding simulation link object.
        """
        self._sim_link_ref2 = link_ref
        self.update_info_text()

    def set_sim_link_ref(self, link_ref: SimLink ):
        """
        Sets the reference to the corresponding simulation link object.
        """
        self._sim_link_ref1 = link_ref

    def update_info_text(self):
        info_str = ""
        if self._sim_link_ref1 and self._sim_link_ref2:
            dump1 = self._sim_link_ref1.dump()
            dump2 = self._sim_link_ref2.dump()

            q1_depth = len(dump1['queue'])
            max1_info = f"max: {dump1['maxDepth']}" if dump1['maxDepth'] > 0 else "max: inf"
            
            q2_depth = len(dump2['queue'])
            max2_info = f"max: {dump2['maxDepth']}" if dump2['maxDepth'] > 0 else "max: inf"
            info1_str = f"{self.start_node.name} -> {self.end_node.name}: Q {q1_depth}/{max1_info.split(': ')[1]}"
            info2_str = f"{self.end_node.name} -> {self.start_node.name}: Q {q2_depth}/{max2_info.split(': ')[1]}"
            info_str = f"{info1_str}\n{info2_str}"
            
            self.info_text_item.setPlainText(info_str)
            self._position_info_text()
        elif self._sim_link_ref1:
            dump1 = self._sim_link_ref1.dump()
            q1_depth = len(dump1['queue'])
            max1_info = f"max: {dump1['maxDepth']}" if dump1['maxDepth'] > 0 else "max: inf"
            info_str = f"{self.start_node.name} -> {self.end_node.name}: Q {q1_depth}/{max1_info.split(': ')[1]}"
            self.info_text_item.setPlainText(info_str)
            self._position_info_text()
        elif self._sim_link_ref2:
            dump2 = self._sim_link_ref2.dump()
            q2_depth = len(dump2['queue'])
            max2_info = f"max: {dump2['maxDepth']}" if dump2['maxDepth'] > 0 else "max: inf"
            info_str = f"{self.end_node.name} -> {self.start_node.name}: Q {q2_depth}/{max2_info.split(': ')[1]}"
            self.info_text_item.setPlainText(info_str)
            self._position_info_text()
        else:
            self.info_text_item.setPlainText("")

    def _position_info_text(self):
        if not (self.start_node and self.end_node):
            return
        mid_x = (self.line().p1().x() + self.line().p2().x()) / 2
        mid_y = (self.line().p1().y() + self.line().p2().y()) / 2
        offset_x = 5
        offset_y = -10 # Position slightly above the line's midpoint
        text_rect = self.info_text_item.boundingRect()
        self.info_text_item.setPos(mid_x - text_rect.width() / 2 + offset_x, mid_y - text_rect.height() / 2 + offset_y)

    def update_position(self):
        """Updates the line's start and end points based on the connected nodes' positions."""
        if self.start_node and self.end_node:
            p1 = self.start_node.center_point()
            p2 = self.end_node.center_point()
            self.setLine(p1.x(), p1.y(), p2.x(), p2.y())
            self._position_info_text() 

    def mousePressEvent(self, event):
        print(f"Link chosen: {self.name} (between {self.start_node.name} and {self.end_node.name})")
        current_pen = self.pen()
        current_pen.setColor(LINK_COLOR_HIGHLIGHT)
        current_pen.setWidth(LINK_THICKNESS_HIGHLIGHT)
        self.setPen(current_pen)
        self.update()

        if self._sim_link_ref1 and self._sim_link_ref2: # should all have two
            combined_link_state = {
                f"Forward ({self.start_node.name} -> {self.end_node.name})": self._sim_link_ref1.dump(),
                f"Backward ({self.end_node.name} -> {self.start_node.name})": self._sim_link_ref2.dump()
            }
            self._detail_window = ToolTipWindow(self, self.name, combined_link_state)
            self._detail_window.delete_item_from_scene.connect(self._parent_window.remove_ui_link)
            self._detail_window.show()
        else:
            print(f"Warning: UILink {self.name} has no associated SimLink(s).")

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
        if isinstance(self.name, int):
            self.name = str(self.name)
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
        
        self.name_text_item = QGraphicsTextItem(self.name, self)
        font = self.name_text_item.font()
        font.setBold(True)
        self.name_text_item.setFont(font)

        self.state_text_item = QGraphicsTextItem("", self)
        state_font = self.state_text_item.font()
        state_font.setPointSize(max(6, state_font.pointSize() - 2))
        self.state_text_item.setFont(state_font)
        self.state_text_item.setTextWidth(NODE_SIZE * 0.8)
        self._center_text()

    def set_sim_node_ref(self, sim_ref: SimNode):
        """
        Sets the reference to the corresponding simulation node object.
        """
        self._sim_node_ref = sim_ref
        self.update_ui_from_sim_state()

    def center_point(self):
        """
        Calculates and returns the global scene coordinates of the node's center.
        """
        return self.scenePos() + self.boundingRect().center()

    def update_ui_from_sim_state(self):
        """Updates the UI node's visual representation and detail window based on its sim node's state."""
        if self._sim_node_ref:
            node_dump = self._sim_node_ref.dump()
            state = node_dump[ "state" ]
            state_display_text = ", ".join(f"{k_short}:{v}" for k_short, v in list(state.items())[:2])
            self.state_text_item.setPlainText(state_display_text)
            self._center_text()

            if self._detail_window and self._detail_window.isVisible():
                self._detail_window.update_item_state_display(state)

    def _center_text(self):
        """Centers the text item within the ellipse."""
        ellipse_rect = self.boundingRect()
        center_x = ellipse_rect.center().x()
        
        name_rect = self.name_text_item.boundingRect()
        name_x = center_x - name_rect.width() / 2
        name_y = ellipse_rect.top() + (ellipse_rect.height() * 0.15) - name_rect.height() / 2
        self.name_text_item.setPos(name_x, name_y)

        state_rect = self.state_text_item.boundingRect()
        state_x = center_x - state_rect.width() / 2
        state_y = self.name_text_item.y() + name_rect.height() + 2 
        self.state_text_item.setPos(state_x, state_y)

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
        self.ui_nodes: dict[str, UINode] = {}
        self.ui_links: dict[str, UILink] = {}

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Simulation GUI")
        self.setGeometry(MAIN_WINDOW_X, MAIN_WINDOW_Y, MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT)

        palette = self.palette()
        palette.setColor(QPalette.Window, COLOR_BACKGROUND_DARK)
        palette.setColor(QPalette.WindowText, COLOR_TEXT_LIGHT)
        palette.setColor(QPalette.Button, QColor(85, 85, 85))
        palette.setColor(QPalette.ButtonText, COLOR_TEXT_LIGHT)
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        self.setPalette(palette)
        
        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setObjectName("outputLog")
        text_edit_palette = self.output_log.palette()
        text_edit_palette.setColor(QPalette.Base, QColor(58, 58, 58))
        text_edit_palette.setColor(QPalette.Text, COLOR_TEXT_LIGHT)
        self.output_log.setPalette(text_edit_palette)

        control_panel_layout = QVBoxLayout()

        # control_panel_layout.addWidget(self._create_node_controls_group())
        # control_panel_layout.addWidget(self._create_link_controls_group())
        control_panel_layout.addWidget(self._create_simulation_controls_group(), 1)
        control_panel_layout.addWidget(self._create_log_group(), 5)

        graphics_view = QGraphicsView(self.scene)
        graphics_view.setRenderHint(QPainter.Antialiasing)
        graphics_view.setMouseTracking(True)
        graphics_view.setRenderHint(QPainter.SmoothPixmapTransform)
        graphics_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        graphics_view_palette = graphics_view.palette()
        graphics_view_palette.setColor(QPalette.Base, QColor(60, 60, 60))
        graphics_view.setPalette(graphics_view_palette)
        graphics_view.setStyleSheet(f"border: 1px solid rgb({COLOR_BORDER_GREY.red()}, {COLOR_BORDER_GREY.green()}, {COLOR_BORDER_GREY.blue()}); border-radius: 5px;")


        main_layout = QHBoxLayout(self)
        main_layout.addLayout(control_panel_layout, 1)
        main_layout.addWidget(graphics_view, 2)

        self.setLayout(main_layout)

    def _create_group_box(self, title: str) -> QGroupBox:
        """Helper to create a QGroupBox with consistent styling."""
        group_box = QGroupBox(title)
        group_box_palette = group_box.palette()
        group_box_palette.setColor(QPalette.Window, COLOR_CONTROL_BACKGROUND)
        group_box_palette.setColor(QPalette.WindowText, COLOR_TEXT_LIGHT)
        group_box.setPalette(group_box_palette)
        
        # Set border for QGroupBox using AI power
        group_box.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid rgb({COLOR_BORDER_GREY.red()}, {COLOR_BORDER_GREY.green()}, {COLOR_BORDER_GREY.blue()});
                border-radius: 5px;
                margin-top: 10px; /* Space for title */
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: rgb({COLOR_TEXT_LIGHT.red()}, {COLOR_TEXT_LIGHT.green()}, {COLOR_TEXT_LIGHT.blue()});
                font-weight: bold;
            }}
        """)
        
        layout = QVBoxLayout(group_box)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(5)
        return group_box

    def _create_node_controls_group(self) -> QGroupBox:
        group_box = self._create_group_box("Node Actions")
        layout = group_box.layout()

        label_node_name = QLabel("Node Name:")
        layout.addWidget(label_node_name)
        self.node_input = QLineEdit()
        self.node_input.setPlaceholderText("e.g., node1")
        line_edit_palette = self.node_input.palette()
        line_edit_palette.setColor(QPalette.Base, QColor(58, 58, 58))
        line_edit_palette.setColor(QPalette.Text, COLOR_TEXT_LIGHT)
        self.node_input.setPalette(line_edit_palette)
        layout.addWidget(self.node_input)

        add_node_button = QPushButton("Add New Node")
        add_node_button.clicked.connect(self._on_add_sim_node_clicked)
        layout.addWidget(add_node_button)
        return group_box

    def _create_link_controls_group(self) -> QGroupBox:
        group_box = self._create_group_box("Link Actions")
        layout = group_box.layout()

        label_peer1 = QLabel("Node 1 Name:")
        layout.addWidget(label_peer1)
        self.peer1_input = QLineEdit()
        self.peer1_input.setPlaceholderText("e.g., n1")
        line_edit_palette = self.peer1_input.palette()
        line_edit_palette.setColor(QPalette.Base, QColor(58, 58, 58))
        line_edit_palette.setColor(QPalette.Text, COLOR_TEXT_LIGHT)
        self.peer1_input.setPalette(line_edit_palette)
        layout.addWidget(self.peer1_input)

        label_peer2 = QLabel("Node 2 Name:")
        layout.addWidget(label_peer2)
        self.peer2_input = QLineEdit()
        self.peer2_input.setPlaceholderText("e.g., n2")
        self.peer2_input.setPalette(line_edit_palette)
        layout.addWidget(self.peer2_input)

        add_link_button = QPushButton("Add New Link")
        add_link_button.clicked.connect(self._on_add_sim_link_clicked)
        layout.addWidget(add_link_button)
        return group_box

    def _create_simulation_controls_group(self) -> QGroupBox:
        group_box = self._create_group_box("Simulation Controls")
        layout = group_box.layout()

        load_topology_label = QLabel("Load Topology from Example:")
        layout.addWidget(load_topology_label)

        self.topology_combo_box = QComboBox()
        self._populate_topology_dropdown() # New method to fill the dropdown
        self.topology_combo_box.activated[str].connect(self._on_topology_selected) # Connect signal
        layout.addWidget(self.topology_combo_box)

        self.dump_filename_input = QLineEdit()
        self.dump_filename_input.setPlaceholderText("Enter filename (e.g., my_topo.yaml)")
        line_edit_palette = self.dump_filename_input.palette() # Get default
        line_edit_palette.setColor(QPalette.Base, QColor(58, 58, 58)) # Set custom base
        line_edit_palette.setColor(QPalette.Text, COLOR_TEXT_LIGHT)   # Set custom text
        self.dump_filename_input.setPalette(line_edit_palette)
        layout.addWidget(self.dump_filename_input)

        dump_topology_button = QPushButton("Dump to File")
        dump_topology_button.clicked.connect(self._on_dump_topology_with_input_name_clicked)
        layout.addWidget(dump_topology_button)

        step_button = QPushButton("Step")
        step_button.clicked.connect(self._controller.step_simulation)
        layout.addWidget(step_button)

        continue_button = QPushButton("Continue")
        continue_button.clicked.connect(self._controller.continue_simulation)
        layout.addWidget(continue_button)

        # add dropdown box here: 
        return group_box
    
    def _on_dump_topology_with_input_name_clicked(self):
        """Handles the 'Dump to File' button click using the QLineEdit for filename."""
        file_name_only = self.dump_filename_input.text().strip()

        if not file_name_only:
            self._controller.log_message("Please enter a filename for the topology dump.")
            return

        if not (file_name_only.endswith(".yaml") or file_name_only.endswith(".yml")):
            if "." in file_name_only: # if there's an extension already, append .yaml
                base, ext = os.path.splitext(file_name_only)
                file_name_only = base + ext + ".yaml" # This might result in something like file.txt.yaml
                file_name_only += ".yaml" # Simpler: just append if not already a YAML extension
            else: # if no extension, assume .yaml
                file_name_only += ".yaml"
        try:
            base_save_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        except:
            base_save_dir = os.getcwd()

        full_file_path = os.path.join(base_save_dir, file_name_only)
        self._controller.log_message(f"Attempting to dump topology to: {full_file_path}")
        self._controller.dump_topology(full_file_path)
        self.dump_filename_input.clear()

    def _populate_topology_dropdown(self):
        """Scans the 'examples' directory for .yaml/.yml files and populates the dropdown."""
        self.topology_combo_box.clear()
        self.topology_combo_box.addItem("Select a topology...", userData=None)

        examples_dir = "examples" # Assuming 'examples' is a subdirectory
        if not os.path.isdir(examples_dir):
            self._controller.log_message(f"Error: '{examples_dir}' directory not found.")
            self.topology_combo_box.setEnabled(False)
            return
        try:
            yaml_files = [
                f for f in os.listdir(examples_dir)
                if os.path.isfile(os.path.join(examples_dir, f)) and (f.endswith(".yaml") or f.endswith(".yml"))
            ]
            if not yaml_files:
                self.topology_combo_box.addItem("No YAML files found.", userData=None)
                self.topology_combo_box.setEnabled(False)
            else:
                self.topology_combo_box.setEnabled(True)
                for file_name in sorted(yaml_files):
                    full_path = os.path.join(examples_dir, file_name)
                    self.topology_combo_box.addItem(file_name, userData=full_path)
        except Exception as e:
            self._controller.log_message(f"Error scanning '{examples_dir}': {e}")
            self.topology_combo_box.setEnabled(False)

    def _on_topology_selected(self, display_text: str):
        """Handles the selection of a topology file from the dropdown."""
        file_path = self.topology_combo_box.currentData()
        if file_path:
            self._controller.log_message(f"Attempting to load: {display_text}")
            self._controller.load_topology(file_path)
        elif display_text != "Select a topology...":
            self._controller.log_message(f"Invalid selection or no file path associated with: {display_text}")
    
    def _create_log_group(self) -> QGroupBox:
        group_box = self._create_group_box("Simulation Log")
        layout = group_box.layout()
        layout.addWidget(self.output_log)
        return group_box
    
    def restart_ui(self):
        """Clears all UI nodes and links and resets the output log."""
        for ui_node_item in list(self.ui_nodes.values()):
            self.remove_ui_node(ui_node_item)
        self.ui_nodes.clear() # Ensure the dictionary is empty
        self.ui_links.clear()
        self.output_log.clear()

    def _on_add_sim_node_clicked(self):
        """Handles the 'Add Sim Node' button click."""
        node_name = self.node_input.text().strip()
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
    
    def add_ui_link(self, sim_link_obj: SimLink, peer1_name: str, peer2_name: str):
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
        sim_link_name = f"{peer1_name}-{peer2_name}"
        if f"{peer2_name}-{peer1_name}" in self.ui_links.keys():
            old_ui_link = self.ui_links[f"{peer2_name}-{peer1_name}"]
            old_ui_link.set_sim_link_ref2(sim_link_obj)
            return # one link per dual
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
            ui_link.update_info_text()
        self.scene.update()

    def remove_ui_link(self, ui_link_item: UILink):
        """
        Removes a UILink from the scene and triggers its removal from the simulation.

        Args:
            ui_link_item: The UILink object to remove.
        """
        if ui_link_item and ui_link_item.scene() == self.scene:
            if ui_link_item.start_node and ui_link_item in ui_link_item.start_node.connected_lines:
                ui_link_item.start_node.connected_lines.remove(ui_link_item)
            if ui_link_item.end_node and ui_link_item in ui_link_item.end_node.connected_lines:
                ui_link_item.end_node.connected_lines.remove(ui_link_item)

            self.scene.removeItem(ui_link_item)
            if ui_link_item.name in self.ui_links:
                del self.ui_links[ui_link_item.name]
                self._controller.remove_sim_link(ui_link_item.name) # Inform controller to remove sim link
            print(f"Removed UI link and requested removal of sim link: {ui_link_item.name}")

    def _on_add_sim_link_clicked(self):
        """Handles the 'Add Sim Link' button click."""
        peer1_name = self.peer1_input.text().strip()
        peer2_name = self.peer2_input.text().strip()

        if not peer1_name or not peer2_name:
            self._controller.log_message("Please enter names for both Peer 1 and Peer 2.")
            return

        # Generate a unique link name. Maybe links don't need names. Idk why I thought they should have them
        link_name = f"link{len(self.ui_links) + 1}"
        
        self._controller.add_sim_link(peer1_name, peer2_name)
        self.peer1_input.clear()
        self.peer2_input.clear()

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
    global_print_output_signal = pyqtSignal(str)

    def __init__(self):
        """Initializes the Controller, setting up the simulation and UI."""
        super().__init__()
        self._topology = Topology()
        self._behaviors = self._topology.behaviors
        self._simulation_generator = None

        self.main_window = MainWindow(self)
        # Connect controller's log signal to main window's log method
        self._original_stdout = sys.stdout # Store original stdout
        self._print_capture_stream = QtOutputStream()
        self._print_capture_stream.text_written.connect(self.global_print_output_signal.emit)

        self.log_message_signal.connect(self.main_window.log_message)
        # self.global_print_output_signal.connect(self.main_window.log_behavior_print_output)

    def load_topology(self, file):
        """Loads topology from yaml files"""
        self.reset_simulation()
        self._topology = loadTopologyFile(file)
        self._simulation_generator = self._topology.step()
        self._link_topology()
        self.log_message(f"Loaded yaml file: {file}")
    
    def dump_topology(self, file):
        """Dump to file"""
        dumpTopologyFile(self._topology, file)

    def _link_topology(self):
        """Generates GUI elements for each top element"""
        for node_name, node in self._topology.nodes.items():
            self.main_window.add_ui_node(node_name, node)
        
        for src, dstList in self._topology.links.items():
            for dst, link in dstList.items():
                self.main_window.add_ui_link(link, src, dst)

    def reset_simulation(self):
        """Resets the entire simulation, clearing UI and re-initializing topology."""
        self.main_window.restart_ui()
        self._topology = Topology()
        self._simulation_generator = None

    def add_sim_node(self, name: str, behaviorKey: str = "hello", state: dict = {'initialized':False}):
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
        
        if behaviorKey not in self._topology.behaviors:
            self.log_message(f"Behavior '{behaviorKey}' doesn't exist.")
            return 
        
        sim_node = self._topology.addNode(name, behaviorName=behaviorKey, state=state if state is not None else {})
        self.main_window.add_ui_node(name, sim_node)
        self.log_message(f"Added simulation node '{name}' with behavior '{behaviorKey}'.")

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

    def add_sim_link(self, peer1_name: str, peer2_name: str):
        """
        Adds a new simulation link between two existing nodes to the topology and its UI representation.

        Args:
            name: The unique name for the new link.
            peer1_name: The name of the first node to connect.
            peer2_name: The name of the second node to connect.
        """
        name = f"{peer2_name}-{peer1_name}"
        if name in self._topology.links:
            self.log_message(f"Link '{name}' already exists in simulation.")
            return
        name = f"{peer1_name}-{peer2_name}"
        if name in self._topology.links:
            self.log_message(f"Link '{name}' already exists in simulation.")
            return

        try:
            sim_link = self._topology.addLink(peer1_name, peer2_name)
            self.main_window.add_ui_link(sim_link, peer1_name, peer2_name)
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
            self.log_message("Simulation not initialized...") # Use self.log_message for controlled logging
            return

        sys.stdout = self._print_capture_stream # Redirect global stdout
        try:
            next(self._simulation_generator)
            self.log_message("\n--- Simulation Step Executed ---") # Goes to dedicated log

            for node_name, sim_node_obj in self._topology.nodes.items():
                is_waiting = node_name in self._topology.waiting
                # This log_message goes to the dedicated simulation log
                self.log_message(f"Node: {sim_node_obj.name}, State: {sim_node_obj.state}, Is waiting: {is_waiting}")

            self.main_window.update_ui_nodes()
            self.main_window.update_ui_links()

        except StopIteration:
            self.log_message("Simulation converged: Nothing left to do.")
            self._simulation_generator = None
        except Exception as e:
            self.log_message(f"Error during simulation step: {e}")
            self._simulation_generator = None
        finally:
            sys.stdout = self._original_stdout # Always restore global stdout

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

    # AI styling
    app_palette = app.palette()
    app_palette.setColor(QPalette.Window, COLOR_BACKGROUND_DARK)
    app_palette.setColor(QPalette.WindowText, COLOR_TEXT_LIGHT)
    app_palette.setColor(QPalette.Button, QColor(85, 85, 85))
    app_palette.setColor(QPalette.ButtonText, COLOR_TEXT_LIGHT)
    app_palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    app_palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(app_palette)
    app.setStyleSheet("QPushButton { border: 1px solid rgb(102, 102, 102); border-radius: 4px; padding: 8px 15px; margin: 3px 0; background-color: rgb(85, 85, 85); color: rgb(255, 255, 255); }"
                      "QPushButton:hover { background-color: rgb(102, 102, 102); }"
                      "QPushButton:pressed { background-color: rgb(68, 68, 68); }")


    controller = Controller()
    controller.main_window.show()

    sys.exit(app.exec_())
