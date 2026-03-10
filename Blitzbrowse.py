import sys
import os
from PyQt6.QtCore import QUrl, Qt, QSize
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QPushButton, QVBoxLayout, QWidget,
    QHBoxLayout, QToolBar, QTabWidget, QLabel, QProgressBar, QListWidget,
    QListWidgetItem, QSplitter
)
from PyQt6.QtGui import QAction, QIcon, QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineSettings, QWebEngineDownloadRequest
)

class DownloadItem(QWidget):
    def __init__(self, download: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        self.download = download
        self.is_paused = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        # File name
        self.name = QLabel(download.downloadFileName() or "Downloading...")
        self.name.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        layout.addWidget(self.name)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        layout.addWidget(self.progress, stretch=1)

        # Status / percent
        self.status = QLabel("0%")
        self.status.setFixedWidth(70)
        self.status.setStyleSheet("color: #aaa;")
        layout.addWidget(self.status)

        # Pause/Resume button
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setFixedWidth(80)
        self.pause_btn.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.setStyleSheet("background: #d32f2f; color: white;")
        cancel_btn.clicked.connect(self.cancel_download)
        layout.addWidget(cancel_btn)

        # Connect signals
        download.downloadProgress.connect(self.on_progress)
        download.finished.connect(self.on_finished)
        download.stateChanged.connect(self.on_state_changed)
        download.isPausedChanged.connect(self.on_paused_changed)

        download.accept()  # Start the download

    def on_progress(self, received, total):
        if total > 0:
            percent = int((received / total) * 100)
            self.progress.setValue(percent)
            self.status.setText(f"{percent}%")

    def on_finished(self):
        self.status.setText("Done ✓")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Done")

    def on_state_changed(self, state):
        if state == QWebEngineDownloadRequest.DownloadInterrupted:
            self.status.setText("Interrupted")
        elif state == QWebEngineDownloadRequest.DownloadCancelled:
            self.status.setText("Cancelled")
            self.pause_btn.setEnabled(False)

    def on_paused_changed(self, paused):
        self.is_paused = paused
        self.pause_btn.setText("Resume" if paused else "Pause")
        self.status.setText("Paused" if paused else self.status.text())

    def toggle_pause(self):
        if self.is_paused:
            self.download.resume()
        else:
            self.download.pause()

    def cancel_download(self):
        self.download.cancel()
        # Optional: remove item from list (parent is QListWidget)
        parent_list = self.parent()
        if isinstance(parent_list, QListWidget):
            idx = parent_list.indexAt(self.pos())
            if idx.isValid():
                parent_list.takeItem(idx.row())

class BlitzBrowse(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlitzBrowse ⚡")
        self.setGeometry(100, 100, 1400, 900)

        # Dark modern style
        self.setStyleSheet("""
            QMainWindow { background: #121212; color: #e0e0e0; }
            QToolBar { background: #1e1e1e; border: none; padding: 6px; }
            QTabWidget::pane { border: 1px solid #333; background: #181818; }
            QTabBar::tab { background: #252525; color: #aaa; padding: 10px 20px; border: none; }
            QTabBar::tab:selected { background: #333; color: white; border-bottom: 3px solid #ff9800; }
            QListWidget { background: #181818; border-top: 1px solid #333; color: #ddd; }
            QPushButton { background: #333; color: white; border: 1px solid #444; padding: 4px 8px; border-radius: 4px; }
            QPushButton:hover { background: #444; }
        """)

        # Profile with persistence
        self.profile = QWebEngineProfile("BlitzProfile", self)
        storage = os.path.join(os.path.expanduser("~"), ".blitz_data")
        self.profile.setPersistentStoragePath(storage)
        self.profile.setCachePath(os.path.join(storage, "cache"))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setHttpUserAgent("Mozilla/5.0 (X11; Linux x86_64) Chrome/128 Safari/537.36 BlitzBrowse/1.0")

        self.profile.downloadRequested.connect(self.on_download)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.sync_url_bar)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        back = QAction(QIcon.fromTheme("go-previous"), "Back", self)
        back.triggered.connect(lambda: self.current_view().back() if self.current_view() else None)
        toolbar.addAction(back)

        fwd = QAction(QIcon.fromTheme("go-next"), "Forward", self)
        fwd.triggered.connect(lambda: self.current_view().forward() if self.current_view() else None)
        toolbar.addAction(fwd)

        refresh = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        refresh.triggered.connect(lambda: self.current_view().reload() if self.current_view() else None)
        toolbar.addAction(refresh)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.go)
        self.url_bar.setPlaceholderText("Search or URL...")
        toolbar.addWidget(self.url_bar)

        go_btn = QPushButton("Go")
        go_btn.setFixedWidth(60)
        go_btn.clicked.connect(self.go)
        toolbar.addWidget(go_btn)

        new_tab = QPushButton("+")
        new_tab.setFixedSize(40, 32)
        new_tab.clicked.connect(self.new_tab)
        toolbar.addWidget(new_tab)

        # Downloads section
        self.downloads = QListWidget()
        self.downloads.setStyleSheet("background: #181818;")
        downloads_header = QLabel("Downloads (Pause/Resume/Cancel)")
        downloads_header.setStyleSheet("font-weight: bold; padding: 10px; background: #222; color: #ff9800;")

        downloads_container = QWidget()
        dl_layout = QVBoxLayout(downloads_container)
        dl_layout.addWidget(downloads_header)
        dl_layout.addWidget(self.downloads)
        dl_layout.setContentsMargins(0, 0, 0, 0)

        # Splitter for tabs + downloads
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.tabs)
        splitter.addWidget(downloads_container)
        splitter.setSizes([700, 180])
        self.setCentralWidget(splitter)

        # Open first tab
        self.new_tab("https://www.google.com")

    def current_view(self):
        return self.tabs.currentWidget()

    def new_tab(self, url="https://www.google.com"):
        view = QWebEngineView()
        page = QWebEnginePage(self.profile, view)
        view.setPage(page)
        view.load(QUrl(url))

        idx = self.tabs.addTab(view, "Loading...")
        view.titleChanged.connect(lambda t: self.tabs.setTabText(idx, t[:35] or "New Tab"))
        view.iconChanged.connect(lambda i: self.tabs.setTabIcon(idx, i))
        view.urlChanged.connect(lambda u: self.sync_url_bar() if self.tabs.currentIndex() == idx else None)

        self.tabs.setCurrentIndex(idx)

    def go(self):
        txt = self.url_bar.text().strip()
        if not txt: return
        if " " in txt and "." not in txt:
            url = f"https://www.google.com/search?q={txt.replace(' ', '+')}"
        else:
            url = txt if txt.startswith(("http://", "https://")) else "https://" + txt
        self.current_view().load(QUrl(url))

    def sync_url_bar(self):
        v = self.current_view()
        if v: self.url_bar.setText(v.url().toString())

    def close_tab(self, idx):
        if self.tabs.count() > 1:
            self.tabs.removeTab(idx)

    def on_download(self, download: QWebEngineDownloadRequest):
        item = DownloadItem(download)
        list_item = QListWidgetItem()
        list_item.setSizeHint(item.sizeHint())
        self.downloads.addItem(list_item)
        self.downloads.setItemWidget(list_item, item)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set application icon (shows in window, taskbar, dock)
    icon_path = os.path.join(os.path.dirname(__file__), "blitzbrowse-icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    w = BlitzBrowse()
    w.show()
    sys.exit(app.exec())
