import sys
import os
import tempfile
import zipfile
import shutil
import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox


class ShellEmulator:
    def __init__(self, user_name, fs_zip_path):
        self.user_name = user_name
        self.fs_zip_path = fs_zip_path
        self.temp_dir = tempfile.mkdtemp(prefix="virtfs_")

        # Извлечение zip-архива во временную директорию
        with zipfile.ZipFile(self.fs_zip_path, 'r') as zf:
            zf.extractall(self.temp_dir)

        # Предполагается, что корнем является поддиректория, например root
        self.root_dir = os.path.join(self.temp_dir, "root")
        if not os.path.exists(self.root_dir):
            # Если root нет, примем temp_dir как root
            self.root_dir = self.temp_dir
        self.current_dir = self.root_dir

    def get_prompt(self):
        # Относительный путь относительно root
        rel_path = os.path.relpath(self.current_dir, self.root_dir)
        if rel_path == ".":
            rel_path = "/"
        else:
            rel_path = "/" + rel_path.replace("\\", "/")  # Для Windows совместимости
        return f"{self.user_name}@virtfs:{rel_path}$ "

    def ls_command(self):
        try:
            entries = os.listdir(self.current_dir)
            entries.sort()
            return "\n".join(entries) if entries else ""
        except Exception as e:
            return f"Ошибка: {e}"

    def cd_command(self, path):
        new_path = self.resolve_path(path)
        if new_path is None:
            return f"Нет такого каталога: {path}"
        elif not os.path.isdir(new_path):
            return f"Не является каталогом: {path}"
        else:
            self.current_dir = new_path
            return ""

    def pwd_command(self):
        # Отобразить путь от "корня" виртуальной ФС
        rel_path = os.path.relpath(self.current_dir, self.root_dir)
        if rel_path == ".":
            rel_path = "/"
        else:
            rel_path = "/" + rel_path.replace("\\", "/")  # Для Windows совместимости
        return rel_path

    def mv_command(self, src, dst):
        src_path = self.resolve_path(src, must_exist=True)
        if src_path is None:
            return f"Нет такого файла или директории: {src}"

        # Проверяем, что источник существует
        if not os.path.exists(src_path):
            return f"Нет такого файла или директории: {src}"

        dst_path = self.resolve_path(dst, must_exist=False)
        if dst_path is None:
            return f"Некорректный путь назначения: {dst}"

        # Если dst - существующая директория, переместим внутрь нее
        if os.path.isdir(dst_path):
            dst_path = os.path.join(dst_path, os.path.basename(src_path))
        else:
            # Если dst не существует, предполагаем, что это новое имя или путь
            parent_dst = os.path.dirname(dst_path)
            if not os.path.isdir(parent_dst):
                return f"Путь назначения не является каталогом: {parent_dst}"

        try:
            shutil.move(src_path, dst_path)
            return ""
        except Exception as e:
            return f"Ошибка перемещения: {e}"

    def exit_command(self):
        # Очистка временной директории
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        return "EXIT"

    def resolve_path(self, path, must_exist=True):
        # Определение, является ли путь абсолютным
        if path.startswith("/"):
            tentative_path = os.path.normpath(os.path.join(self.root_dir, path.lstrip("/")))
        else:
            tentative_path = os.path.normpath(os.path.join(self.current_dir, path))

        # Проверка, что tentative_path находится внутри root_dir
        if os.path.commonpath([self.root_dir, tentative_path]) != self.root_dir:
            return None  # Попытка выйти за пределы виртуальной ФС

        if must_exist and not os.path.exists(tentative_path):
            return None

        return tentative_path

    def run_command(self, command_line):
        parts = command_line.strip().split()
        if len(parts) == 0:
            return ""
        cmd = parts[0]
        args = parts[1:]

        if cmd == "ls":
            return self.ls_command()
        elif cmd == "cd":
            if len(args) == 0:
                return "Введите каталог"  # Изменение поведения при отсутствии аргумента
            else:
                return self.cd_command(args[0])
        elif cmd == "pwd":
            return self.pwd_command()
        elif cmd == "mv":
            if len(args) < 2:
                return "Использование: mv <источник> <назначение>"
            return self.mv_command(args[0], args[1])
        elif cmd == "exit":
            return self.exit_command()
        else:
            return f"Команда не найдена: {cmd}"


class ShellGUI:
    def __init__(self, emulator):
        self.emulator = emulator

        self.root = tk.Tk()
        self.root.title("Shell Emulator")

        self.text_area = scrolledtext.ScrolledText(self.root, width=80, height=24, state='disabled')
        self.text_area.pack(pady=5)

        self.entry = tk.Entry(self.root, width=80)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.pack(pady=5)

        self.run_button = tk.Button(self.root, text="Run", command=self.execute_command)
        self.run_button.pack(pady=5)

        # Показать начальный prompt
        self.show_prompt()

    def show_prompt(self):
        prompt = self.emulator.get_prompt()
        self.append_text(prompt)

    def append_text(self, text):
        self.text_area.config(state='normal')
        self.text_area.insert(tk.END, text)
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END)

    def on_enter(self, event):
        self.execute_command()

    def execute_command(self):
        cmd = self.entry.get()
        if cmd.strip():
            self.append_text(cmd + "\n")
            result = self.emulator.run_command(cmd)
            if result == "EXIT":
                self.root.quit()
                return
            if result:
                self.append_text(result + "\n")
        self.entry.delete(0, tk.END)
        self.show_prompt()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python emulator.py <имя_пользователя> <путь_к_zip>")
        sys.exit(1)

    user_name = sys.argv[1]
    fs_zip_path = sys.argv[2]

    # Проверка существования zip-архива
    if not os.path.isfile(fs_zip_path):
        print(f"Файл не найден: {fs_zip_path}")
        sys.exit(1)

    try:
        emulator = ShellEmulator(user_name, fs_zip_path)
    except zipfile.BadZipFile:
        print(f"Некорректный zip-архив: {fs_zip_path}")
        sys.exit(1)

    gui = ShellGUI(emulator)
    gui.run()