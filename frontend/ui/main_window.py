import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QStackedWidget,
    QComboBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from ui.api_client import ApiClient


class LoginWidget(QWidget):
    """Login/Register widget."""

    def __init__(self, api_client: ApiClient, on_success=None):
        super().__init__()
        self.api_client = api_client
        self.on_success = on_success
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("Exoterra ID")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel("Autentificare secură cu parolă")
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        form_layout = QFormLayout()

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("+40 7XX XXX XXX sau email@exemplu.com")
        form_layout.addRow("Telefon sau Email:", self.id_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Minim 8 caractere")
        form_layout.addRow("Parolă:", self.password_input)

        layout.addLayout(form_layout)
        layout.addSpacing(15)

        button_layout = QHBoxLayout()
        self.login_btn = QPushButton("Intră în cont")
        self.login_btn.setStyleSheet("background-color: #00d4ff; color: black; font-weight: bold; padding: 8px;")
        self.login_btn.clicked.connect(self.on_login_click)
        button_layout.addWidget(self.login_btn)

        self.register_btn = QPushButton("Creează cont")
        self.register_btn.setStyleSheet("background-color: #333; color: white; padding: 8px;")
        self.register_btn.clicked.connect(self.on_register_click)
        button_layout.addWidget(self.register_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

        self.setLayout(layout)

    def on_login_click(self):
        identifier = self.id_input.text().strip()
        password = self.password_input.text()

        if not identifier or not password:
            QMessageBox.warning(self, "Validare", "Completează toate câmpurile!")
            return

        if len(password) < 8:
            QMessageBox.warning(self, "Validare", "Parola trebuie să aibă minim 8 caractere.")
            return

        email = identifier if "@" in identifier else None
        phone = identifier if "@" not in identifier else None

        try:
            self.api_client.login(email=email, phone=phone, password=password)
            QMessageBox.information(self, "Succes", f"Bine ai venit, {identifier}!")
            if self.on_success:
                self.on_success()
        except Exception as e:
            QMessageBox.critical(self, "Eroare la autentificare", str(e))

    def on_register_click(self):
        identifier = self.id_input.text().strip()
        password = self.password_input.text()

        if not identifier or not password:
            QMessageBox.warning(self, "Validare", "Completează toate câmpurile!")
            return

        if len(password) < 8:
            QMessageBox.warning(self, "Validare", "Parola trebuie să aibă minim 8 caractere.")
            return

        email = identifier if "@" in identifier else None
        phone = identifier if "@" not in identifier else None

        try:
            self.api_client.register(email=email, phone=phone, password=password)
            QMessageBox.information(self, "Succes", "Cont creat cu succes!")
            if self.on_success:
                self.on_success()
        except Exception as e:
            QMessageBox.critical(self, "Eroare la înregistrare", str(e))


class DashboardWidget(QWidget):
    """Dashboard widget after login."""

    def __init__(self, api_client: ApiClient, on_logout=None):
        super().__init__()
        self.api_client = api_client
        self.on_logout = on_logout
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("YourCar Dashboard")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        layout.addSpacing(10)

        user_info_group = QGroupBox("Informații utilizator")
        user_form = QFormLayout()

        user_id_label = QLabel(f"ID: {self.api_client.user_id}")
        user_form.addRow("User ID:", user_id_label)

        email_label = QLabel(self.api_client.email or "—")
        user_form.addRow("Email:", email_label)

        phone_label = QLabel(self.api_client.phone or "—")
        user_form.addRow("Telefon:", phone_label)

        user_info_group.setLayout(user_form)
        layout.addWidget(user_info_group)

        layout.addSpacing(20)

        car_info_group = QGroupBox("YourCar Index")
        car_form = QFormLayout()

        car_id_label = QLabel("YCR-2024-001")
        car_form.addRow("Vehicle ID:", car_id_label)

        score_label = QLabel("89,67%")
        score_label_font = QFont()
        score_label_font.setPointSize(14)
        score_label_font.setBold(True)
        score_label.setFont(score_label_font)
        car_form.addRow("YourCar Score:", score_label)

        car_info_group.setLayout(car_form)
        layout.addWidget(car_info_group)

        layout.addSpacing(20)

        logout_btn = QPushButton("Logout")
        logout_btn.setStyleSheet("background-color: #ff4444; color: white; padding: 8px;")
        logout_btn.clicked.connect(self.on_logout_click)
        layout.addWidget(logout_btn)

        layout.addStretch()
        self.setLayout(layout)

    def on_logout_click(self):
        self.api_client.clear_token()
        if self.on_logout:
            self.on_logout()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.api_client = ApiClient("http://localhost:8000")
        self.setWindowTitle("Mulberry - YourCar")
        self.setGeometry(100, 100, 500, 600)

        self.stacked_widget = QStackedWidget()

        self.login_widget = LoginWidget(self.api_client, on_success=self.show_dashboard)
        self.dashboard_widget = DashboardWidget(self.api_client, on_logout=self.show_login)

        self.stacked_widget.addWidget(self.login_widget)
        self.stacked_widget.addWidget(self.dashboard_widget)

        self.setCentralWidget(self.stacked_widget)

        self.check_backend()

    def check_backend(self):
        """Check if backend is available."""
        if not self.api_client.health_check():
            QMessageBox.critical(
                self,
                "Eroare",
                "Backend-ul nu este disponibil!\n\nAsigură-te că ai rulat:\npython -m backend.main"
            )

    def show_login(self):
        self.stacked_widget.setCurrentWidget(self.login_widget)
        self.login_widget.id_input.clear()
        self.login_widget.password_input.clear()

    def show_dashboard(self):
        self.dashboard_widget = DashboardWidget(self.api_client, on_logout=self.show_login)
        self.stacked_widget.replaceWidget(self.stacked_widget.widget(1), self.dashboard_widget)
        self.stacked_widget.setCurrentWidget(self.dashboard_widget)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
