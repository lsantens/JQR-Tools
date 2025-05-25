import sys
import json
import subprocess
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QStackedWidget, QHBoxLayout, QTextEdit
)

class ConfigCollector:
    def __init__(self):
        self.data = {
            "network": {},
            "robot": {},
            "ssh": {}
        }

    def save_to_file(self):
        with open(os.path.join(os.path.dirname(__file__), "robot_config_bundle.json"), "w") as f:
            json.dump(self.data, f, indent=4)

    def load_from_file(self):
        try:
            with open("robot_config_bundle.json", "r") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            pass

collector = ConfigCollector()

class NetworkConfigPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.fields = {}
        for label in ["SSID", "Password", "Gateway"]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            input_box = QLineEdit()
            self.fields[label] = input_box
            row.addWidget(lbl)
            row.addWidget(input_box)
            layout.addLayout(row)

        mask_row = QHBoxLayout()
        self.mask_label = QLabel("Subnet Mask")
        self.mask_input = QLineEdit("255.255.255.0")
        self.mask_inc = QPushButton("+")
        self.mask_dec = QPushButton("-")
        self.mask_inc.clicked.connect(lambda: self.adjust_mask(1))
        self.mask_dec.clicked.connect(lambda: self.adjust_mask(-1))
        mask_row.addWidget(self.mask_label)
        mask_row.addWidget(self.mask_input)
        mask_row.addWidget(self.mask_inc)
        mask_row.addWidget(self.mask_dec)
        layout.addLayout(mask_row)

        self.fields["Subnet Mask"] = self.mask_input
        self.fields["Gateway"].textChanged.connect(self.update_ip_prefix)

        button_layout = QVBoxLayout()
        self.load_btn = QPushButton("Load Config")
        self.save_btn = QPushButton("Save Network Config")
        self.push_btn = QPushButton("Push Config")
        self.load_btn.clicked.connect(self.load_config)
        self.save_btn.clicked.connect(self.save_config)
        self.push_btn.clicked.connect(self.push_config)

        button_column = QVBoxLayout()
        button_column.addWidget(self.load_btn)
        button_column.addWidget(self.save_btn)
        button_column.addWidget(self.push_btn)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addLayout(button_column)
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
        collector.data["network"] = {key: field.text() for key, field in self.fields.items()}
        collector.save_to_file()

    def update_ip_prefix(self):
        gateway = self.fields["Gateway"].text()
        parts = gateway.strip().split(".")
        if len(parts) == 4:
            prefix = ".".join(parts[:3]) + "."
            robot_page = self.parent().parent().pages.get("Robot Info")
            if robot_page:
                existing = robot_page.ip_input.text()
                ip_parts = existing.split(".")
                last = ip_parts[-1] if len(ip_parts) == 4 else "100"
                robot_page.ip_input.setText(prefix + last)

    def push_config(self):
        import paramiko
        import os

        collector.save_to_file()
        collector.load_from_file()

        ip = "192.168.0.100"
        username = collector.data.get("ssh", {}).get("username", "")
        password = collector.data.get("ssh", {}).get("password", "")

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password)

            sftp = ssh.open_sftp()
            local_bundle = os.path.join(os.path.dirname(__file__), "robot_config_bundle.json")
            local_script = os.path.join(os.path.dirname(__file__), "apply_config.py")
            sftp.put(local_bundle, "/home/hairou/robot_config_bundle.json")
            sftp.put(local_script, "/home/hairou/apply_config.py")
            sftp.close()

            stdin, stdout, stderr = ssh.exec_command("python3 /home/hairou/apply_config.py")
            output = stdout.read().decode()
            error = stderr.read().decode()
            if output:
                print("Config applied:", output)
            if error:
                print("Errors:", error)
            ssh.close()
        except Exception as e:
            print(f"SSH push error: {e}")

    def load_config(self):
        collector.load_from_file()
        for key, field in self.fields.items():
            field.setText(collector.data.get("network", {}).get(key, ""))

class RobotInfoPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.ip_label = QLabel("Robot IP")
        self.ip_input = QLineEdit()
        self.robot_id_label = QLabel("Robot Number")
        robot_row = QHBoxLayout()
        self.robot_id_input = QLineEdit()
        self.increment_btn = QPushButton("+")
        self.decrement_btn = QPushButton("-")
        robot_row.addWidget(self.robot_id_input)
        robot_row.addWidget(self.increment_btn)
        robot_row.addWidget(self.decrement_btn)

        self.sync_toggle = QPushButton("IP Mirroring: ON")
        self.sync_toggle.setCheckable(True)
        self.sync_toggle.setChecked(True)
        self.sync_toggle.clicked.connect(self.toggle_sync)

        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)
        layout.addWidget(self.sync_toggle)
        layout.addWidget(self.robot_id_label)
        layout.addLayout(robot_row)

        self.load_btn = QPushButton("Load Robot Config")
        self.save_btn = QPushButton("Save Robot Info")
        self.load_btn.clicked.connect(self.load_info)
        self.save_btn.clicked.connect(self.save_info)
        layout.addWidget(self.load_btn)
        layout.addWidget(self.load_btn)
        layout.addWidget(self.save_btn)

        self.increment_btn.clicked.connect(self.increment_robot_number)
        self.decrement_btn.clicked.connect(self.decrement_robot_number)

        self.setLayout(layout)

    def increment_robot_number(self):
        try:
            num = int(self.robot_id_input.text())
            self.robot_id_input.setText(str(num + 1))
            if self.sync_toggle.isChecked():
                self.update_ip(1)
        except ValueError:
            pass
        except ValueError:
            pass

    def decrement_robot_number(self):
        try:
            num = int(self.robot_id_input.text())
            self.robot_id_input.setText(str(num - 1))
            if self.sync_toggle.isChecked():
                self.update_ip(-1)
        except ValueError:
            pass
        except ValueError:
            pass

    def update_ip(self, delta):
        ip = self.ip_input.text().strip()
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                parts[-1] = str(max(0, int(parts[-1]) + delta))
                self.ip_input.setText(".".join(parts))
            except ValueError:
                pass

    def sync_robot_number(self):
        if not self.sync_toggle.isChecked():
            return
        ip = self.ip_input.text()
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                self.robot_id_input.setText(str(int(parts[-1])))
            except ValueError:
                pass

        # always allow user to enter a number
        self.robot_id_input.setReadOnly(False)

    def toggle_sync(self):
        if self.sync_toggle.isChecked():
            self.sync_toggle.setText("IP Mirroring: ON")
            self.sync_robot_number()
        else:
            self.sync_toggle.setText("IP Mirroring: OFF")
        if self.sync_toggle.isChecked():
            self.sync_toggle.setText("IP Mirroring: ON")
        else:
            self.sync_toggle.setText("IP Mirroring: OFF")

    def load_info(self):
        collector.load_from_file()
        self.robot_id_input.setText(collector.data.get("robot", {}).get("robot_number", ""))
        self.ip_input.setText(collector.data.get("robot", {}).get("ip", ""))

    def save_info(self):
        collector.data["robot"] = {
            "robot_number": self.robot_id_input.text(),
            "ip": self.ip_input.text()
        }
        collector.save_to_file()

class SystemPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        # SSH output display for status/logs
        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)

        self.connect_btn = QPushButton("Connect via SSH")
        self.connect_btn.clicked.connect(self.connect_ssh)

        layout.addWidget(self.status_display)
        layout.addWidget(self.connect_btn)

        self.reboot_btn = QPushButton("Reboot Robot")
        self.reboot_btn.clicked.connect(self.confirm_reboot)
        layout.addWidget(self.reboot_btn)

        self.setLayout(layout)

    def confirm_reboot(self):
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, 'Confirm Reboot', 'Are you sure you want to reboot the robot?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.reboot()

    def reboot(self):
        try:
            result = subprocess.run(
                ["/bin/bash", "/kubot/home/app/app.sh", "restart"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.status_display.append("Robot rebooted via app.sh restart command.")
            else:
                self.status_display.append("Failed to reboot robot:" + result.stderr)
        except Exception as e:
            self.status_display.append(f"Error during reboot: {str(e)}")

    def connect_ssh(self):
        collector.load_from_file()
        ip = collector.data.get("robot", {}).get("ip", "")
        user = collector.data.get("ssh", {}).get("username", "")

        if not ip or not user:
            self.status_display.append("Missing IP or SSH Username in config.")
            return

        self.status_display.append(f"Attempting SSH to {user}@{ip}...")

        try:
            result = subprocess.run([
                "ssh", f"{user}@{ip}", "echo Connected Successfully"
            ], capture_output=True, timeout=5, text=True)

            if result.returncode == 0:
                self.status_display.append("SSH Success:" + result.stdout)
            else:
                self.status_display.append("SSH Failed:" + result.stderr)
        except Exception as e:
            self.status_display.append(f"Error: {str(e)}")

    def reboot(self):
        try:
            result = subprocess.run(
                ["/bin/bash", "/kubot/home/app/app.sh", "restart"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.status_display.append("Robot rebooted via app.sh restart command.")
            else:
                self.status_display.append("Failed to reboot robot:" + result.stderr)
        except Exception as e:
            self.status_display.append(f"Error during reboot: {str(e)}")

    def connect_ssh(self):
        collector.load_from_file()
        ip = collector.data.get("robot", {}).get("ip", "")
        user = collector.data.get("ssh", {}).get("username", "")

        if not ip or not user:
            self.status_display.append("Missing IP or SSH Username in config.")
            return

        self.status_display.append(f"Attempting SSH to {user}@{ip}...")

        try:
            result = subprocess.run([
                "ssh", f"{user}@{ip}", "echo Connected Successfully"
            ], capture_output=True, timeout=5, text=True)

            if result.returncode == 0:
                self.status_display.append("SSH Success:\n" + result.stdout)
            else:
                self.status_display.append("SSH Failed:\n" + result.stderr)
        except Exception as e:
            self.status_display.append(f"Error: {str(e)}")

class SSHConfigPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.username_label = QLabel("SSH Username")
        self.username_input = QLineEdit("hairou")
        self.password_label = QLabel("SSH Password")
        self.password_input = QLineEdit("HairouKubot_@2018!")
        self.password_input.setEchoMode(QLineEdit.Normal)

        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        self.load_btn = QPushButton("Load SSH Credentials")
        self.save_btn = QPushButton("Save SSH Credentials")
        self.load_btn.clicked.connect(self.load_credentials)
        self.save_btn.clicked.connect(self.save_credentials)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)

    def load_credentials(self):
        collector.load_from_file()
        self.username_input.setText(collector.data.get("ssh", {}).get("username", ""))
        self.password_input.setText(collector.data.get("ssh", {}).get("password", ""))

    def save_credentials(self):
        collector.data["ssh"] = {
            "username": self.username_input.text(),
            "password": self.password_input.text()
        }
        collector.save_to_file()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot Configurator")

        self.stack = QStackedWidget()
        self.pages = {
            "System": SystemPage(),
            "Network Config": NetworkConfigPage(),
            "Robot Info": RobotInfoPage(),
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
    main_win.resize(500, 400)
    main_win.show()
    sys.exit(app.exec_())
