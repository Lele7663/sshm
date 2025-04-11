#!/usr/bin/env python3
import json
import os
import curses
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
import argparse

@dataclass
class SSHConfig:
    name: str
    host: str
    port: int
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None
    group: Optional[str] = None  # Format: "parent/child/subgroup"

    @property
    def group_parts(self) -> List[str]:
        if not self.group:
            return []
        return self.group.split('/')

    @property
    def group_name(self) -> str:
        if not self.group:
            return ""
        return self.group.split('/')[-1]

class SSHManager:
    def __init__(self, config_dir: str = "~/.ssh-manager"):
        self.config_dir = Path(config_dir).expanduser()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.key_file = self.config_dir / ".key"
        self._load_or_create_key()
        self._load_config()

    def _load_or_create_key(self):
        if self.key_file.exists():
            self.key = self.key_file.read_bytes()
        else:
            self.key = Fernet.generate_key()
            self.key_file.write_bytes(self.key)
        self.cipher_suite = Fernet(self.key)

    def _load_config(self):
        if self.config_file.exists():
            encrypted_data = self.config_file.read_bytes()
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            config_data = json.loads(decrypted_data)
            self.configs = [SSHConfig(**config) for config in config_data]
        else:
            self.configs = []

    def _save_config(self):
        config_data = [asdict(config) for config in self.configs]
        encrypted_data = self.cipher_suite.encrypt(json.dumps(config_data).encode())
        self.config_file.write_bytes(encrypted_data)

    def decrypt_config(self) -> str:
        """Decrypt and return the config file contents as a formatted string."""
        if not self.config_file.exists():
            return "No config file found."
        
        try:
            encrypted_data = self.config_file.read_bytes()
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            config_data = json.loads(decrypted_data)
            
            # Format the config data nicely
            formatted_data = []
            for config in config_data:
                formatted_config = []
                formatted_config.append(f"Name: {config['name']}")
                formatted_config.append(f"Host: {config['host']}")
                formatted_config.append(f"Port: {config['port']}")
                formatted_config.append(f"Username: {config['username']}")
                if config.get('password'):
                    formatted_config.append("Password: [encrypted]")
                if config.get('key_path'):
                    formatted_config.append(f"Key Path: {config['key_path']}")
                if config.get('group'):
                    formatted_config.append(f"Group: {config['group']}")
                formatted_data.append("\n".join(formatted_config))
            
            return "\n\n".join(formatted_data)
        except Exception as e:
            return f"Error decrypting config: {str(e)}"

    def add_config(self, config: SSHConfig):
        # Remove existing config with same name if it exists
        self.remove_config(config.name)
        
        # Add the new config
        self.configs.append(config)
        self._save_config()

    def remove_config(self, name: str):
        self.configs = [c for c in self.configs if c.name != name]
        self._save_config()

    def get_config(self, name: str) -> Optional[SSHConfig]:
        for config in self.configs:
            if config.name == name:
                return config
        return None

    def get_group_tree(self) -> Dict:
        """Returns a hierarchical structure of groups and their configs."""
        tree = {}
        
        # First, create the group structure
        for config in self.configs:
            if not config.group:
                if "Ungrouped" not in tree:
                    tree["Ungrouped"] = []
                tree["Ungrouped"].append(config)
                continue
                
            parts = config.group.split('/')
            current = tree
            
            # Create the group hierarchy
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Add the config to the final group
            if parts[-1] not in current:
                current[parts[-1]] = []
            current[parts[-1]].append(config)
        
        return tree

    def get_all_groups(self) -> List[str]:
        """Returns a flat list of all group paths."""
        groups = set()
        for config in self.configs:
            if config.group:
                groups.add(config.group)
        return sorted(list(groups))

    def get_group_configs(self, group_path: str) -> List[SSHConfig]:
        """Returns all configs in a specific group."""
        if not group_path:
            return [c for c in self.configs if not c.group]
        return [c for c in self.configs if c.group == group_path]

    def get_parent_groups(self, group_path: str) -> List[str]:
        """Returns all parent groups of a given group path."""
        if not group_path:
            return []
        parts = group_path.split('/')
        parents = []
        current = ''
        for part in parts[:-1]:
            current = current + '/' + part if current else part
            parents.append(current)
        return parents

    def get_child_groups(self, group_path: str) -> List[str]:
        """Returns all direct child groups of a given group path."""
        if not group_path:
            return [g for g in self.get_all_groups() if '/' not in g]
        return [g for g in self.get_all_groups() if g.startswith(group_path + '/') and '/' not in g[len(group_path)+1:]]

    def count_group_items(self, group_path: str) -> int:
        """Counts total number of items (configs and subgroups) in a group."""
        count = 0
        # Count configs in this group
        count += len(self.get_group_configs(group_path))
        # Count subgroups
        count += len(self.get_child_groups(group_path))
        return count

class SSHManagerUI:
    def __init__(self):
        self.ssh_manager = SSHManager()
        self.current_index = 0
        self.mode = "list"  # list, add, edit, confirm_delete
        self.editing_config = None
        self.input_fields = ["name", "host", "port", "username", "password", "key_path", "group"]
        self.current_field = 0
        self.input_values = {field: "" for field in self.input_fields}
        self.message = ""
        self.message_timeout = 0
        self.delete_confirm = None
        self.current_path = []  # Current path in the group tree
        self.display_items = []  # List of items to display (groups and configs)
        self.password_visible = False  # Track password visibility state
        self.colors_initialized = False

    def init_colors(self):
        if not self.colors_initialized:
            curses.start_color()
            curses.use_default_colors()
            # Initialize color pairs with transparent background
            curses.init_pair(1, curses.COLOR_WHITE, -1)  # Normal text
            curses.init_pair(2, curses.COLOR_BLUE, -1)   # Highlight
            curses.init_pair(3, curses.COLOR_CYAN, -1)   # Dim text
            self.colors_initialized = True

    def _build_display_items(self):
        """Build the list of items to display, including groups and configs."""
        self.display_items = []
        current_group = '/'.join(self.current_path) if self.current_path else None

        # Add parent directory if not at root
        if self.current_path:
            self.display_items.append(("..", "dir", None))

        # Add child groups
        child_groups = self.ssh_manager.get_child_groups(current_group)
        for group in sorted(child_groups):
            group_name = group.split('/')[-1]
            count = self.ssh_manager.count_group_items(group)
            self.display_items.append((f"{group_name} ({count})", "dir", group))

        # Add configs in current group
        configs = self.ssh_manager.get_group_configs(current_group)
        for config in sorted(configs, key=lambda x: x.name):
            self.display_items.append((f"{config.name} ({config.host})", "config", config))

    def draw_list(self, stdscr):
        self.init_colors()
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        # Draw header
        header = "SSH Manager"
        if self.current_path:
            header += f" - {'/'.join(self.current_path)}"
        stdscr.addstr(0, (w - len(header)) // 2, header, curses.color_pair(1))
        
        # Build and draw items
        self._build_display_items()
        
        if not self.display_items:
            stdscr.addstr(1, 0, "No items found. Press 'a' to add a connection.", curses.color_pair(1))
        else:
            for i, (item, item_type, data) in enumerate(self.display_items):
                if i == self.current_index:
                    if item_type == "dir":
                        if item == "..":
                            prefix = "> "
                            suffix = ""
                        else:
                            prefix = "> ["
                            suffix = "]"
                    else:
                        prefix = "> "
                        suffix = ""
                    stdscr.addstr(i + 1, 0, f"{prefix}{item}{suffix}", curses.color_pair(2) | curses.A_REVERSE)
                else:
                    if item_type == "dir":
                        if item == "..":
                            prefix = "  "
                            suffix = ""
                        else:
                            prefix = "  ["
                            suffix = "]"
                    else:
                        prefix = "  "
                        suffix = ""
                    stdscr.addstr(i + 1, 0, f"{prefix}{item}{suffix}", curses.color_pair(1))
        
        # Draw help text at the bottom
        help_text = "↑↓: Navigate | c: Connect | s: SFTP | a: Add | e: Edit | d: Delete | q: Quit"
        stdscr.addstr(h - 1, 2, help_text, curses.color_pair(3))
        
        # Draw message if any
        if self.message and self.message_timeout > 0:
            stdscr.addstr(h - 2, 2, self.message, curses.color_pair(1))
            self.message_timeout -= 1
            if self.message_timeout == 0:
                self.message = ""
        
        stdscr.refresh()

    def draw_add_form(self, stdscr):
        self.init_colors()
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        # Draw title
        title = "Add New Connection" if not self.editing_config else "Edit Connection"
        stdscr.addstr(0, (w - len(title)) // 2, title, curses.color_pair(1))
        
        # Draw fields
        for i, field in enumerate(self.input_fields):
            y = 2 + i * 2
            if y >= h - 2:
                break
                
            # Draw field label
            label = f"{field.capitalize()}: "
            stdscr.addstr(y, 2, label, curses.color_pair(1))
            
            # Draw input value
            value = self.input_values[field]
            if field == "password" and not self.password_visible:
                value = "*" * len(value)
            
            # Highlight current field
            if i == self.current_field:
                stdscr.addstr(y, 2 + len(label), value, curses.color_pair(2) | curses.A_REVERSE)
                # Add help text for password field with highlight only when selected
                if field == "password":
                    help_text = "Press Ctrl+T to toggle password visibility"
                    stdscr.addstr(y + 1, 2, help_text, curses.color_pair(2) | curses.A_REVERSE)
            else:
                stdscr.addstr(y, 2 + len(label), value, curses.color_pair(1))
        
        # Draw help text
        help_text = "Enter: Save | Esc: Cancel | ↑↓: Navigate"
        stdscr.addstr(h - 1, 2, help_text, curses.color_pair(3))
        
        # Draw message if any
        if self.message:
            stdscr.addstr(h - 2, 2, self.message, curses.color_pair(1))

    def draw_confirm_delete(self, stdscr):
        self.init_colors()
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        # Draw confirmation message
        config = self.delete_confirm
        message = f"Delete connection '{config.name}' ({config.host})? [y/N]"
        stdscr.addstr(0, 0, message, curses.color_pair(1))
        
        # Draw message if any
        if self.message and self.message_timeout > 0:
            stdscr.addstr(h-1, 0, self.message, curses.color_pair(1))
            self.message_timeout -= 1
            if self.message_timeout == 0:
                self.message = ""
        
        stdscr.refresh()

    def show_message(self, message: str, timeout: int = 3):
        self.message = message
        self.message_timeout = timeout

    def handle_list_input(self, stdscr, key):
        if key == curses.KEY_UP and self.current_index > 0:
            self.current_index -= 1
        elif key == curses.KEY_DOWN and self.current_index < len(self.display_items) - 1:
            self.current_index += 1
        elif key == 10:  # Enter
            if self.display_items:
                item, item_type, data = self.display_items[self.current_index]
                if item_type == "dir":
                    if item == "..":
                        if self.current_path:
                            self.current_path.pop()
                            self.current_index = 0
                    else:
                        self.current_path.append(item.split(" (")[0])
                        self.current_index = 0
                else:
                    # Handle config selection
                    self.editing_config = data
                    self.mode = "edit"
                    self.input_values = {
                        "name": data.name,
                        "host": data.host,
                        "port": str(data.port),
                        "username": data.username,
                        "password": data.password or "",
                        "key_path": data.key_path or "",
                        "group": data.group or ""
                    }
                    self.current_field = 0
        elif key == ord('a'):
            self.mode = "add"
            self.input_values = {field: "" for field in self.input_fields}
            # Pre-fill the group field with current path
            if self.current_path:
                self.input_values["group"] = '/'.join(self.current_path)
            self.current_field = 0
        elif key == ord('e') and self.display_items:
            item, item_type, data = self.display_items[self.current_index]
            if item_type == "config":
                self.editing_config = data
                self.mode = "edit"
                self.input_values = {
                    "name": data.name,
                    "host": data.host,
                    "port": str(data.port),
                    "username": data.username,
                    "password": data.password or "",
                    "key_path": data.key_path or "",
                    "group": data.group or ""
                }
                self.current_field = 0
        elif key == ord('d') and self.display_items:
            item, item_type, data = self.display_items[self.current_index]
            if item_type == "config":
                self.mode = "confirm_delete"
                self.delete_confirm = data
        elif key == ord('q'):
            curses.curs_set(1)
            curses.echo()
            curses.endwin()
            return False
        elif key == ord('c') and self.display_items:
            item, item_type, data = self.display_items[self.current_index]
            if item_type == "config":
                self.show_message(f"Connecting to {data.host}...")
                self.connect_to_ssh(data)
        elif key == ord('s') and self.display_items:
            item, item_type, data = self.display_items[self.current_index]
            if item_type == "config":
                self.show_message(f"Starting SFTP session with {data.host}...")
                self.connect_to_sftp(data)
        return True

    def handle_add_input(self, stdscr, key):
        if key == curses.KEY_UP and self.current_field > 0:
            self.current_field -= 1
        elif key == curses.KEY_DOWN and self.current_field < len(self.input_fields) - 1:
            self.current_field += 1
        elif key == 27:  # Esc
            self.mode = "list"
            self.editing_config = None
        elif key == 20:  # Ctrl+T (ASCII 20)
            if self.input_fields[self.current_field] == "password":
                self.password_visible = not self.password_visible
        elif key == 10:  # Enter
            try:
                config = SSHConfig(
                    name=self.input_values["name"],
                    host=self.input_values["host"],
                    port=int(self.input_values["port"]),
                    username=self.input_values["username"],
                    password=self.input_values["password"] or None,
                    key_path=self.input_values["key_path"] or None,
                    group=self.input_values["group"] or None
                )
                
                if self.mode == "edit":
                    # Remove old config and add new one
                    self.ssh_manager.remove_config(self.editing_config.name)
                    self.ssh_manager.add_config(config)
                    self.show_message(f"Updated connection: {config.name}")
                else:
                    self.ssh_manager.add_config(config)
                    self.show_message(f"Added connection: {config.name}")
                
                self.mode = "list"
                self.editing_config = None
            except ValueError as e:
                self.show_message(f"Error: {str(e)}")
        elif key >= 32 and key <= 126:  # Printable characters
            field = self.input_fields[self.current_field]
            self.input_values[field] += chr(key)
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace
            field = self.input_fields[self.current_field]
            self.input_values[field] = self.input_values[field][:-1]
        return True

    def handle_confirm_delete(self, stdscr, key):
        if key == ord('y'):
            config = self.delete_confirm
            self.ssh_manager.remove_config(config.name)
            if self.current_index >= len(self.display_items):
                self.current_index = max(0, len(self.display_items) - 1)
            self.show_message(f"Deleted connection: {config.name}")
        elif key == ord('n') or key == 27:  # 'n' or Esc
            self.show_message("Deletion cancelled")
        else:
            return True  # Ignore other keys
        
        self.mode = "list"
        self.delete_confirm = None
        return True

    def connect_to_ssh(self, config: SSHConfig):
        # Build SSH command
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no"]
        
        # Add port if not default
        if config.port != 22:
            cmd.extend(["-p", str(config.port)])
        
        # Add identity file if specified
        if config.key_path:
            cmd.extend(["-i", config.key_path])
        
        # Add username and host
        cmd.append(f"{config.username}@{config.host}")
        
        # End curses and restore terminal state
        curses.endwin()
        curses.curs_set(1)  # Show cursor
        curses.echo()       # Enable echo
        
        try:
            if config.password:
                # Use sshpass for password authentication
                cmd = ["sshpass", "-e"] + cmd
                # Set the password as an environment variable
                env = os.environ.copy()
                env["SSHPASS"] = config.password
            
                # Execute SSH command in a new process
                process = subprocess.Popen(cmd, env=env)
                process.wait()
            else:
                # Execute SSH command in a new process without password
                process = subprocess.Popen(cmd)
                process.wait()
            
            # Restart curses
            stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.curs_set(0)
            stdscr.keypad(1)
            
            if process.returncode != 0:
                if process.returncode == 6:
                    self.show_message("Authentication failed - check username and password")
                else:
                    self.show_message(f"Connection failed with exit code {process.returncode}")
            else:
                self.show_message("Connection closed")
                
        except Exception as e:
            print(f"Connection failed: {str(e)}")
            if config.password:
                print("Note: Make sure 'sshpass' is installed on your system.")
                print("On Ubuntu/Debian: sudo apt-get install sshpass")
                print("On Fedora: sudo dnf install sshpass")
                print("On Arch: sudo pacman -S sshpass")
            
            # Restart curses
            stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.curs_set(0)
            stdscr.keypad(1)

    def connect_to_sftp(self, config: SSHConfig):
        # Build SFTP command
        cmd = ["sftp", "-o", "StrictHostKeyChecking=no"]
        
        # Add port if not default
        if config.port != 22:
            cmd.extend(["-P", str(config.port)])
        
        # Add identity file if specified
        if config.key_path:
            cmd.extend(["-i", config.key_path])
        
        # Add username and host
        cmd.append(f"{config.username}@{config.host}")
        
        # End curses and restore terminal state
        curses.endwin()
        curses.curs_set(1)  # Show cursor
        curses.echo()       # Enable echo
        
        try:
            if config.password:
                # Use sshpass for password authentication
                cmd = ["sshpass", "-e"] + cmd
                # Set the password as an environment variable
                env = os.environ.copy()
                env["SSHPASS"] = config.password
            
                # Execute SFTP command in a new process
                process = subprocess.Popen(cmd, env=env)
                process.wait()
            else:
                # Execute SFTP command in a new process without password
                process = subprocess.Popen(cmd)
                process.wait()
            
            # Restart curses
            stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.curs_set(0)
            stdscr.keypad(1)
            
            if process.returncode != 0:
                if process.returncode == 6:
                    self.show_message("Authentication failed - check username and password")
                else:
                    self.show_message(f"SFTP connection failed with exit code {process.returncode}")
            else:
                self.show_message("SFTP connection closed")
                
        except Exception as e:
            print(f"SFTP connection failed: {str(e)}")
            if config.password:
                print("Note: Make sure 'sshpass' is installed on your system.")
                print("On Ubuntu/Debian: sudo apt-get install sshpass")
                print("On Fedora: sudo dnf install sshpass")
                print("On Arch: sudo pacman -S sshpass")
            
            # Restart curses
            stdscr = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.curs_set(0)
            stdscr.keypad(1)

    def run(self, stdscr):
        try:
            curses.curs_set(0)  # Hide cursor
            stdscr.keypad(1)    # Enable keypad mode
            
            running = True
            while running:
                try:
                    if self.mode == "list":
                        self.draw_list(stdscr)
                        running = self.handle_list_input(stdscr, stdscr.getch())
                    elif self.mode in ["add", "edit"]:
                        self.draw_add_form(stdscr)
                        running = self.handle_add_input(stdscr, stdscr.getch())
                    elif self.mode == "confirm_delete":
                        self.draw_confirm_delete(stdscr)
                        running = self.handle_confirm_delete(stdscr, stdscr.getch())
                except KeyboardInterrupt:
                    # Handle Ctrl+C during input
                    self.mode = "list"
                    self.show_message("Operation cancelled")
                    continue
        finally:
            # Only restore terminal state if we haven't already
            try:
                curses.curs_set(1)  # Show cursor
                curses.echo()       # Enable echo
                curses.endwin()     # End curses mode
            except curses.error:
                pass  # Ignore errors if curses is already ended

def main():
    parser = argparse.ArgumentParser(description='SSH Manager')
    parser.add_argument('--show-config', action='store_true', help='Show decrypted config contents')
    args = parser.parse_args()
    
    if args.show_config:
        manager = SSHManager()
        print(manager.decrypt_config())
        return
    
    ui = SSHManagerUI()
    try:
        curses.wrapper(ui.run)
    except KeyboardInterrupt:
        # Handle Ctrl+C at the top level
        pass
    except Exception as e:
        # Handle any other exceptions
        print(f"Error: {str(e)}")
        try:
            curses.endwin()
            curses.curs_set(1)
            curses.echo()
        except curses.error:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
