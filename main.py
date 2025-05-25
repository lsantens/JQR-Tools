import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QStackedWidget, QHBoxLayout
)

class NetworkConfigPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.fields = {}
        for label in ["SSID", "Password", "IP Address", "Subnet Mask", "Gateway"]:
            lbl = QLabel(label)
            input_box = QLineEdit()
            self.fields[label] = input_box
            layout.addWidget(lbl)
            layout.addWidget(input_box)

        self.save_btn = QPushButton("Save Network Config")
        self.save_btn.clicked.connect(self.save_config)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

    def save_config(self):
        config_data = {key: field.text() for key, field in self.fields.items()}
        with open("network_profile.conf", "w") as f:
            for key, val in config_data.items():
                f.write(f"{key}={val}\n")

class RobotInfoPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.robot_id_label = QLabel("Robot Number")
        self.robot_id_input = QLineEdit()
        self.ip_label = QLabel("Robot IP")
        self.ip_input = QLineEdit()

        layout.addWidget(self.robot_id_label)
        layout.addWidget(self.robot_id_input)
        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)

        self.save_btn = QPushButton("Save Robot Info")
        self.save_btn.clicked.connect(self.save_info)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

    def save_info(self):
        robot_info = {
            "robot_number": self.robot_id_input.text(),
            "ip": self.ip_input.text()
        }
        with open("robot_info.json", "w") as f:
            json.dump(robot_info, f, indent=4)

class SystemPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.reboot_btn = QPushButton("Reboot Robot")
        self.reboot_btn.clicked.connect(self.reboot)
        layout.addWidget(self.reboot_btn)

        self.setLayout(layout)

    def reboot(self):
        import os
        os.system("sudo reboot")

class SSHConfigPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.username_label = QLabel("SSH Username")
        self.username_input = QLineEdit()
        self.password_label = QLabel("SSH Password")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        self.save_btn = QPushButton("Save SSH Credentials")
        self.save_btn.clicked.connect(self.save_credentials)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

    def save_credentials(self):
        ssh_info = {
            "username": self.username_input.text(),
            "password": self.password_input.text()
        }
        with open("ssh_credentials.conf", "w") as f:
            for key, val in ssh_info.items():
                f.write(f"{key}={val}\n")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot Configurator")

        self.stack = QStackedWidget()
        self.pages = {
            "Network Config": NetworkConfigPage(),
            "Robot Info": RobotInfoPage(),
            "System": SystemPage(),
            "SSH Config": SSHConfigPage()
        }

        for page in self.pages.values():
            self.stack.addWidget(page)

        self.buttons = QHBoxLayout()
        for name, page in self.pages.items():
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, n=name: self.switch_page(n))
            self.buttons.addWidget(btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(self.buttons)
        main_layout.addWidget(self.stack)
        self.setLayout(main_layout)

    def switch_page(self, name):
        index = list(self.pages.keys()).index(name)
        self.stack.setCurrentIndex(index)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.resize(400, 300)
    main_win.show()
    sys.exit(app.exec_())
