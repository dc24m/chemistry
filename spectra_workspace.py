"""Native workspace layout helpers; figure and processing state stay in ControlPanel."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QToolButton, QScrollArea, QTabWidget, QSizePolicy,
    QLabel, QGroupBox,
)


def collapse_section(group: QGroupBox, expanded: bool = False):
    """Make an existing group collapsible without changing control ownership APIs."""
    title = group.title()
    content = QWidget()
    content.setObjectName('sectionContent')
    content.setLayout(group.layout())
    group.setTitle('')
    group.setObjectName('workspaceSection')
    layout = QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    toggle = QToolButton(group)
    toggle.setObjectName('sectionToggle')
    # A bare '&' is a keyboard mnemonic on buttons ('Files & traces' -> 'Files_traces').
    toggle.setText(title.replace('&', '&&'))
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    toggle.setCheckable(True)
    toggle.setChecked(expanded)
    toggle.setAccessibleName(title)
    toggle.setToolTip('Expand or collapse ' + title.lower())

    def set_expanded(on):
        content.setVisible(on)
        toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    toggle.toggled.connect(set_expanded)
    layout.addWidget(toggle)
    layout.addWidget(content)
    set_expanded(expanded)
    group.toggle = toggle
    group.content = content
    return group


def arrange_workspace(panel, layout, pages):
    """Rehome existing control groups into three independently scrolling pages."""
    while layout.count():
        layout.takeAt(0)
    layout.setContentsMargins(0, 0, 0, 0)
    panel.workspace_tabs = QTabWidget(panel)
    panel.workspace_tabs.setObjectName('workspaceTabs')
    panel.workspace_tabs.setDocumentMode(True)
    panel.workspace_tabs.tabBar().setExpanding(True)
    panel.workspace_pages = {}
    panel.workspace_scrolls = {}
    panel.sections = {}
    for name, groups in pages:
        page = QWidget()
        page.setObjectName('workspacePage')
        page.setMinimumWidth(0)
        page.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        column = QVBoxLayout(page)
        column.setContentsMargins(10, 10, 10, 12)
        column.setSpacing(10)
        for group, expanded in groups:
            title = group.title()
            panel.sections[title] = collapse_section(group, expanded)
            group.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
            column.addWidget(group)
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        panel.workspace_tabs.addTab(scroll, name)
        panel.workspace_pages[name] = page
        panel.workspace_scrolls[name] = scroll
    # Existing long scientific hints must wrap when the sidebar is resized.
    for label in panel.findChildren(QLabel):
        if label.objectName() in ('hint', 'fieldlbl') and label.maximumWidth() > 1000:
            label.setWordWrap(True)
    layout.addWidget(panel.workspace_tabs)
