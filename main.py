import sys
import os
import json
import paramiko
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QStackedWidget, QHBoxLayout, QMessageBox, QTextEdit, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt
import subprocess
# ---------------------- Scrollable Config ---------------------
class ScrollablePage(QWidget):
    def __init__(self, inner_widget):
        super().__init__()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner_widget)
        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

# ---------------------- Config Collector ----------------------
class ConfigCollector:
    def __init__(self):
        self.data = {
            "network": {},
            "robot": {},
            "ssh": {}
        }

    def save_to_file(self):
        with open("robot_config_bundle.json", "w") as f:
            json.dump(self.data, f, indent=4)

    def load_from_file(self):
        try:
            with open("robot_config_bundle.json", "r") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            pass

collector = ConfigCollector()

# ---------------------- Utility ----------------------
def generate_sed_command(config_key, sub_key, new_value):
    json_path = "/home/kubot/app/config__software-design.json"
    safe_value = str(new_value).replace("/", "\\/").replace("\"", "\\\"")
    return (
        f"sudo su -c \"sed -i '/\\\"{config_key}\\\"/,/\\}}/ s/\\\"{sub_key}\\\": .*$/\\\"{sub_key}\\\": \\\"{safe_value}\\\",/' {json_path}\""
    )

# ---------------------- Network Config Page ----------------------
class NetworkConfigPage(QWidget):
    def __init__(self, pages_ref=None):
        super().__init__()
        self.pages = pages_ref
        layout = QVBoxLayout()
        self.fields = {}

        for label in ["SSID", "Password", "Gateway"]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            input_box = QLineEdit()
            self.setStyleSheet("QWidget { font-size: 10pt; }")
            self.fields[label] = input_box
            row.addWidget(lbl)
            row.addWidget(input_box)
            layout.addLayout(row)

        self.fields["Gateway"].textChanged.connect(self.update_ip_prefix)
        # Subnet Mask
        mask_row = QHBoxLayout()
        lbl = QLabel("Subnet Mask")

        self.mask_input = QLineEdit("255.255.255.0")
        self.mask_input.setMaximumWidth(140)  # reduced width

        self.mask_inc = QPushButton("+")
        self.mask_dec = QPushButton("-")

        # Slightly larger buttons
        self.mask_inc.setMinimumSize(100, 26)
        self.mask_dec.setMinimumSize(100, 26)

        self.mask_inc.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.mask_dec.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.mask_inc.clicked.connect(lambda: self.adjust_mask(1))
        self.mask_dec.clicked.connect(lambda: self.adjust_mask(-1))

        mask_row.addWidget(lbl)
        mask_row.addWidget(self.mask_input)
        mask_row.addWidget(self.mask_inc)
        mask_row.addWidget(self.mask_dec)
        layout.addLayout(mask_row)

        self.fields["Subnet Mask"] = self.mask_input

        # Buttons
        self.load_btn = QPushButton("Load")
        self.save_btn = QPushButton("Save")
        self.push_btn = QPushButton("Push Config via SSH")

        self.load_btn.clicked.connect(self.load_config)
        self.save_btn.clicked.connect(self.save_config)
        self.push_btn.clicked.connect(self.push_config)

        button_row = QHBoxLayout()
        button_row.addWidget(self.load_btn)
        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.push_btn)

        layout.addLayout(button_row)
        self.setLayout(layout)

    def adjust_mask(self, delta):
        parts = self.mask_input.text().split(".")
        if len(parts) == 4:
            try:
                third = int(parts[2]) + delta
                parts[2] = str(min(255, max(0, third)))
                self.mask_input.setText(".".join(parts))
            except ValueError:
                pass

    def save_config(self):
        collector.data["network"] = {k: v.text() for k, v in self.fields.items()}
        collector.save_to_file()

    def load_config(self):
        collector.load_from_file()
        net = collector.data.get("network", {})
        for k, field in self.fields.items():
            field.setText(net.get(k, ""))

    def update_ip_prefix(self):
        gateway = self.fields["Gateway"].text().strip()
        parts = gateway.split(".")
        if len(parts) == 4:
            prefix = ".".join(parts[:3]) + "."
            robot_page = self.pages.get("Robot Info")
            if robot_page:
                # unwrap: ScrollablePage → layout → scroll → widget (RobotInfoPage)
                robot_widget = robot_page.layout().itemAt(0).widget().widget()
                current_ip = robot_widget.ip_input.text()
                if current_ip and len(current_ip.split(".")) == 4:
                    last = current_ip.split(".")[-1]
                else:
                    last = "100"

                robot_widget.ip_input.setText(prefix + last)

    def push_config(self):
        collector.load_from_file()
        net = collector.data.get("network", {})
        rob = collector.data.get("robot", {})
        ssh = collector.data.get("ssh", {})

        ip = ssh.get("ip", "")
        username = ssh.get("username", "")
        password = ssh.get("password", "")

        if not ip or not username or not password:
            QMessageBox.warning(self, "Error", "Missing IP/Username/Password.")
            return

        commands = [
            generate_sed_command("network", "ssid", net.get("SSID", "")),
            generate_sed_command("network", "password", net.get("Password", "")),
            generate_sed_command("network", "gateway", net.get("Gateway", "")),
            generate_sed_command("network", "subnet_mask", net.get("Subnet Mask", "")),
            generate_sed_command("robot", "ip", rob.get("ip", "")),
            generate_sed_command("robot", "robot_number", rob.get("robot_number", "")),
            generate_sed_command("network", "server", rob.get("ess_ip", ""))  # Now sourced from robot info
        ]

        try:
            ssh_conn = paramiko.SSHClient()
            ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_conn.connect(ip, username=username, password=password)
            for cmd in commands:
                ssh_conn.exec_command(cmd)
            ssh_conn.close()
            QMessageBox.information(self, "Success", "Configuration pushed successfully.")
        except Exception as e:
            QMessageBox.critical(self, "SSH Error", str(e))

# ---------------------- Robot Info Page ----------------------
class RobotInfoPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QWidget { font-size: 10pt; }")
        layout = QVBoxLayout()

        # Row for IP and Robot Number
        ip_row = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g. 10.1.220.45")
        self.robot_id_input = QLineEdit()
        self.robot_id_input.setPlaceholderText("Robot Number on Sticker")
        ip_row.addWidget(QLabel("IP:"))
        ip_row.addWidget(self.ip_input)
        ip_row.addWidget(QLabel("ID:"))
        ip_row.addWidget(self.robot_id_input)
        layout.addLayout(ip_row)

        # ESS IP row
        ess_row = QHBoxLayout()
        self.ess_input = QLineEdit()
        self.ess_input.setPlaceholderText("ESS Server VIP")
        ess_row.addWidget(QLabel("ESS IP:"))
        ess_row.addWidget(self.ess_input)
        layout.addLayout(ess_row)

        # Mirror toggle and +/- buttons on same row, spread evenly
        control_row = QHBoxLayout()

        self.mirror_btn = QPushButton("Mirror On")
        self.mirror_btn.setCheckable(True)
        self.mirror_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mirror_btn.toggled.connect(self.toggle_mirror)

        self.dec_btn = QPushButton("-")
        self.dec_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dec_btn.clicked.connect(lambda: self.adjust(-1))

        self.inc_btn = QPushButton("+")
        self.inc_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.inc_btn.clicked.connect(lambda: self.adjust(1))

        control_row.addWidget(self.mirror_btn)
        control_row.addWidget(self.dec_btn)
        control_row.addWidget(self.inc_btn)
        layout.addLayout(control_row)

        # Save and Load buttons
        save = QPushButton("Save")
        load = QPushButton("Load")
        save.clicked.connect(self.save_info)
        load.clicked.connect(self.load_info)
        layout.addWidget(load)
        layout.addWidget(save)

        self.setLayout(layout)

    def toggle_mirror(self, checked):
        if checked:
            ip = self.ip_input.text().strip().split(".")
            if len(ip) == 4 and ip[-1].isdigit():
                self.robot_id_input.setText(ip[-1])
        self.mirror_btn.setText("Mirror On" if checked else "Mirror Off")

    def adjust(self, delta):
        try:
            number = int(self.robot_id_input.text()) + delta
            self.robot_id_input.setText(str(number))
        except:
            return

        if self.mirror_btn.isChecked():
            ip = self.ip_input.text().strip().split(".")
            if len(ip) == 4 and ip[-1].isdigit():
                ip[-1] = str(max(0, min(255, int(ip[-1]) + delta)))
                self.ip_input.setText(".".join(ip))

    def save_info(self):
        collector.data["robot"] = {
            "robot_number": self.robot_id_input.text(),
            "ip": self.ip_input.text(),
            "ess_ip": self.ess_input.text()
        }
        collector.save_to_file()

    def load_info(self):
        collector.load_from_file()
        rob = collector.data.get("robot", {})
        self.robot_id_input.setText(rob.get("robot_number", ""))
        self.ip_input.setText(rob.get("ip", ""))
        self.ess_input.setText(rob.get("ess_ip", ""))



# ---------------------- System Page ----------------------
class SystemPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QWidget { font-size: 10pt; }")
        layout = QVBoxLayout()

        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)

        self.connect_btn = QPushButton("Connect via SSH")
        self.connect_btn.clicked.connect(self.connect_ssh)

        self.reboot_btn = QPushButton("Reboot Robot")
        self.reboot_btn.clicked.connect(self.reboot)

        self.push_btn = QPushButton("Push Config")
        self.push_btn.clicked.connect(self.push_config)

        layout.addWidget(self.status_display)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.reboot_btn)
        layout.addWidget(self.push_btn)

        self.setLayout(layout)

    def connect_ssh(self):
        collector.load_from_file()
        ip = collector.data.get("ssh", {}).get("ip", "")
        user = collector.data.get("ssh", {}).get("username", "")
        if not ip or not user:
            self.status_display.append("Missing IP or SSH Username.")
            return
        self.status_display.append(f"Attempting SSH to {user}@{ip}...")

        try:
            result = subprocess.run(["ssh", f"{user}@{ip}", "echo Connected"],
                                    capture_output=True, timeout=5, text=True)
            if result.returncode == 0:
                self.status_display.append("SSH Success:\n" + result.stdout)
            else:
                self.status_display.append("SSH Failed:\n" + result.stderr)
        except Exception as e:
            self.status_display.append(f"Error: {str(e)}")

    def reboot(self):
        self.status_display.append("Reboot command placeholder (implement if needed).")

    def push_config(self):
        self.status_display.append("Push Config button pressed.")


# ---------------------- SSH Config Page ----------------------
from PyQt5.QtWidgets import QFrame

class SSHConfigPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QWidget { font-size: 10pt; }")
        self.setFocusPolicy(Qt.NoFocus)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g. 192.168.0.101")

        self.username_input = QLineEdit("kubot")
        self.password_input = QLineEdit("HairouKubot_@2018!")
        self.password_input.setEchoMode(QLineEdit.Normal)

        layout.addWidget(QLabel("IP Address"))
        layout.addWidget(self.ip_input)
        layout.addWidget(QLabel("Username"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(self.password_input)

        # Buttons in one row
        button_row = QHBoxLayout()
        load = QPushButton("Load")
        save = QPushButton("Save")
        load.clicked.connect(self.load_credentials)
        save.clicked.connect(self.save_credentials)
        button_row.addWidget(load)
        button_row.addWidget(save)

        layout.addLayout(button_row)
        self.setLayout(layout)

    def save_credentials(self):
        collector.data["ssh"] = {
            "ip": self.ip_input.text(),
            "username": self.username_input.text(),
            "password": self.password_input.text()
        }
        collector.save_to_file()

    def load_credentials(self):
        collector.load_from_file()
        ssh = collector.data.get("ssh", {})
        self.ip_input.setText(ssh.get("ip", ""))
        self.username_input.setText(ssh.get("username", ""))
        self.password_input.setText(ssh.get("password", ""))



# ---------------------- Main App ----------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot Configurator")
        self.setFixedSize(480, 280)  # Crucial for Pi screen

        self.stack = QStackedWidget()
        self.pages = {}

        # Initialize all pages with access to `self.pages`
        self.pages["System"] = ScrollablePage(SystemPage())
        self.pages["Network Config"] = ScrollablePage(NetworkConfigPage(pages_ref=self.pages))
        self.pages["Robot Info"] = ScrollablePage(RobotInfoPage())
        self.pages["SSH Config"] = ScrollablePage(SSHConfigPage())
        # self.pages["SSH Config"] = SSHConfigPage()

        for page in self.pages.values():
            self.stack.addWidget(page)

        # Button layout (smaller)
        buttons = QHBoxLayout()
        for name in self.pages:
            btn = QPushButton(name)
            btn.setMinimumHeight(24)
            btn.setStyleSheet("font-size: 9pt;")
            btn.clicked.connect(lambda _, n=name: self.switch_page(n))
            buttons.addWidget(btn)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addLayout(buttons)
        layout.addWidget(self.stack)
        self.setLayout(layout)

    def switch_page(self, name):
        self.stack.setCurrentIndex(list(self.pages.keys()).index(name))



# ---------------------- Run ----------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

