import sys
import json
import subprocess
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
        self.load_btn.clicked.connect(self.load_config)  # fixed here
        self.save_btn = QPushButton("Save Network Config")
        self.save_btn.clicked.connect(self.save_config)

        button_column = QVBoxLayout()
        button_column.addWidget(self.load_btn)
        button_column.addWidget(self.save_btn)

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

    def load_config(self):
        collector.load_from_file()
        network = collector.data.get("network", {})
        for key, field in self.fields.items():
            field.setText(network.get(key, ""))

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



class SystemPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)

        self.connect_btn = QPushButton("Connect via SSH")
        self.connect_btn.clicked.connect(self.connect_ssh)
        self.disconnect_btn = QPushButton("Disconnect SSH")
        self.disconnect_btn.clicked.connect(lambda: self.status_display.append("Disconnected from SSH."))

        self.reboot_btn = QPushButton("Reboot Robot")
        self.reboot_btn.clicked.connect(self.confirm_reboot)

        self.push_btn = QPushButton("Push Config")
        self.push_btn.clicked.connect(self.push_config)

        layout.addWidget(self.status_display)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.disconnect_btn)
        layout.addWidget(self.reboot_btn)
        layout.addWidget(self.push_btn)

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
            result = subprocess.run([
                "/bin/bash", "/kubot/home/app/app.sh", "restart"
            ], capture_output=True, text=True, timeout=10)
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

    def push_config(self):
        page = self.parent().parent().pages.get("Network Config")
        if page:
            page.push_config()


class RobotInfoPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.ip_label = QLabel("Robot IP")
        self.ip_input = QLineEdit()
        self.robot_id_label = QLabel("Robot Number")
        self.robot_id_input = QLineEdit()

        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)
        layout.addWidget(self.robot_id_label)
        layout.addWidget(self.robot_id_input)

        # Mirror toggle
        self.mirror_btn = QPushButton("Mirror On")
        self.mirror_on = False
        self.mirror_btn.setCheckable(True)
        self.mirror_btn.toggled.connect(self.toggle_mirror)

        # Increment and Decrement buttons
        inc_dec_layout = QHBoxLayout()
        self.inc_btn = QPushButton("+")
        self.dec_btn = QPushButton("-")
        self.inc_btn.clicked.connect(lambda: self.adjust_value(1))
        self.dec_btn.clicked.connect(lambda: self.adjust_value(-1))
        inc_dec_layout.addWidget(self.dec_btn)
        inc_dec_layout.addWidget(self.inc_btn)

        layout.addWidget(self.mirror_btn)
        layout.addLayout(inc_dec_layout)

        # Save/Load buttons
        self.save_btn = QPushButton("Save Robot Info")
        self.save_btn.clicked.connect(self.save_info)
        self.load_btn = QPushButton("Load Robot Info")
        self.load_btn.clicked.connect(self.load_info)

        layout.addWidget(self.load_btn)
        layout.addWidget(self.save_btn)
        self.setLayout(layout)

    def toggle_mirror(self, checked):
        self.mirror_on = checked
        self.mirror_btn.setText("Mirror On" if checked else "Mirror Off")
        if checked:
            ip_parts = self.ip_input.text().strip().split(".")
            if len(ip_parts) == 4 and ip_parts[-1].isdigit():
                self.robot_id_input.setText(ip_parts[-1])

    def adjust_value(self, delta):
        # Adjust robot number
        try:
            robot_num = int(self.robot_id_input.text()) + delta
            self.robot_id_input.setText(str(robot_num))
        except ValueError:
            return

        # Adjust IP if mirroring
        if self.mirror_on:
            ip_parts = self.ip_input.text().strip().split(".")
            if len(ip_parts) == 4 and ip_parts[-1].isdigit():
                try:
                    new_ip_last = int(ip_parts[-1]) + delta
                    new_ip_last = max(0, min(255, new_ip_last))
                    ip_parts[-1] = str(new_ip_last)
                    self.ip_input.setText(".".join(ip_parts))
                except ValueError:
                    pass

    def save_info(self):
        collector.data["robot"] = {
            "robot_number": self.robot_id_input.text(),
            "ip": self.ip_input.text()
        }
        collector.save_to_file()

    def load_info(self):
        collector.load_from_file()
        self.robot_id_input.setText(collector.data.get("robot", {}).get("robot_number", ""))
        self.ip_input.setText(collector.data.get("robot", {}).get("ip", ""))

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
        layout.addWidget(self.load_btn)
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
    import os

    app = QApplication(sys.argv)
    collector = ConfigCollector()
    main_win = MainWindow()
    main_win.resize(500, 400)
    main_win.show()
    sys.exit(app.exec_())
