import sys
import os
import zipfile
import shutil
import tempfile
import tkinter as tk
from tkinter import scrolledtext


class ShellEmulator:
    def __init__(self, user_name, fs_zip_path):
        self.user_name = user_name
        self.fs_zip_path = fs_zip_path
        self.zip_file = zipfile.ZipFile(self.fs_zip_path, 'a')  # Открываем в режиме добавления для модификации
        self.current_dir = "/"  # Текущая директория

    def get_prompt(self):
        return f"{self.user_name}@virtfs:{self.current_dir}$ "

    def ls_command(self):
        entries = self._list_dir(self.current_dir)
        return "\n".join(entries) if entries else ""

    def cd_command(self, path):
        new_path = self.resolve_path(path)
        if new_path is None:
            return f"Нет такого каталога: {path}"
        if not self._is_dir(new_path):
            return f"Не является каталогом: {path}"
        self.current_dir = new_path
        return ""

    def pwd_command(self):
        return self.current_dir

    def mv_command(self, src, dst):
        src_path = self.resolve_path(src)
        dst_path = self.resolve_path(dst, is_dst=True)

        if src_path is None:
            return f"Нет такого файла или директории: {src}"
        if dst_path is None:
            return f"Некорректный путь назначения: {dst}"

        # Проверяем, существует ли источник
        if not self._path_exists(src_path):
            return f"Нет такого файла или директории: {src}"

        # Проверяем, является ли назначение директорией
        if self._is_dir(dst_path):
            dst_path = os.path.join(dst_path, os.path.basename(src_path)).replace("\\", "/")

        try:
            self._rename_in_zip(src_path, dst_path)
            return ""
        except Exception as e:
            return f"Ошибка перемещения: {e}"

    def exit_command(self):
        self.zip_file.close()
        return "EXIT"

    def resolve_path(self, path, is_dst=False):
        if path.startswith("/"):
            tentative_path = os.path.normpath(path)
        else:
            tentative_path = os.path.normpath(os.path.join(self.current_dir, path))

        # Убедимся, что путь начинается с '/'
        if not tentative_path.startswith("/"):
            tentative_path = "/" + tentative_path

        # Нормализуем путь для директорий
        if is_dst and not tentative_path.endswith("/"):
            # Мы не знаем, является ли это директорией, оставляем как есть
            pass
        elif self._is_dir(tentative_path):
            if not tentative_path.endswith("/"):
                tentative_path += "/"

        # Возвращаем путь с нормализованными разделителями
        return tentative_path.replace("\\", "/")

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
                return "Введите каталог"
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

    def _list_dir(self, directory):
        directory = directory.rstrip("/") + "/"
        entries = set()
        for name in self.zip_file.namelist():
            if name.startswith(directory.lstrip("/")) and name != directory.lstrip("/"):
                remainder = name[len(directory.lstrip("/")):]
                parts = remainder.split('/', 1)
                entries.add(parts[0])
        return sorted(entries)

    def _is_dir(self, path):
        path = path.rstrip("/") + "/"
        for name in self.zip_file.namelist():
            if name.startswith(path.lstrip("/")):
                return True
        return False

    def _path_exists(self, path):
        if path.endswith("/"):
            return self._is_dir(path)
        return path.lstrip("/").replace("\\", "/") in self.zip_file.namelist()

    def _rename_in_zip(self, src, dst):
        # zipfile не поддерживает переименование, поэтому создадим временный архив
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(temp_fd)
        with zipfile.ZipFile(temp_path, 'w') as temp_zip:
            for item in self.zip_file.infolist():
                item_path = "/" + item.filename  # Убедимся, что путь начинается с '/'
                if item_path.startswith(src if src.endswith("/") else src + "/") or item_path == src:
                    # Вычисляем новый путь
                    if item_path == src:
                        new_item_path = dst
                    else:
                        new_item_path = dst.rstrip("/") + "/" + item_path[len(src):]
                    new_item_path = new_item_path.lstrip("/")
                    # Читаем данные и записываем по новому пути
                    data = self.zip_file.read(item.filename)
                    temp_zip.writestr(new_item_path, data)
                else:
                    # Копируем без изменений
                    temp_zip.writestr(item, self.zip_file.read(item.filename))
        self.zip_file.close()
        shutil.move(temp_path, self.fs_zip_path)
        self.zip_file = zipfile.ZipFile(self.fs_zip_path, 'a')


class ShellGUI:
    def __init__(self, emulator):
        self.emulator = emulator

        self.root = tk.Tk()
        self.root.title("Shell Emulator")

        self.text_area = scrolledtext.ScrolledText(self.root, width=80, height=24)
        self.text_area.pack(pady=5)
        self.text_area.bind("<Key>", self.on_key_press)
        self.text_area.bind("<Return>", self.on_enter)
        self.text_area.bind("<BackSpace>", self.on_backspace)
        self.text_area.bind("<Control-c>", lambda e: "break")  # Отключаем Ctrl+C
        self.text_area.bind("<Button-1>", self.on_mouse_click)
        self.text_area.focus_set()

        # Сделать текстовое поле только для чтения, кроме текущей строки ввода
        self.prompt = self.emulator.get_prompt()
        self.insert_prompt()

    def insert_prompt(self):
        self.text_area.insert(tk.END, self.prompt)
        self.text_area.mark_set("input_start", tk.INSERT)

    def on_key_press(self, event):
        # Разрешаем ввод только в конце текста
        if self.text_area.compare(tk.INSERT, "<", "input_start"):
            self.text_area.mark_set(tk.INSERT, tk.END)
        return

    def on_backspace(self, event):
        # Запрещаем удаление текста перед prompt
        if self.text_area.compare(tk.INSERT, "<=", "input_start"):
            return "break"

    def on_mouse_click(self, event):
        # Запрещаем перемещение курсора в предыдущий текст
        self.text_area.mark_set(tk.INSERT, tk.END)
        return "break"

    def on_enter(self, event):
        command = self.text_area.get("input_start", tk.END).strip()
        self.text_area.insert(tk.END, "\n")
        result = self.emulator.run_command(command)
        if result == "EXIT":
            self.root.quit()
            return "break"
        if result:
            self.text_area.insert(tk.END, result + "\n")
        self.prompt = self.emulator.get_prompt()
        self.insert_prompt()
        return "break"

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
