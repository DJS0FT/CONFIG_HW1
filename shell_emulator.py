import sys
import os
import zipfile
import shutil
import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox

class ShellEmulator:
    def __init__(self, user_name, fs_zip_path):
        self.user_name = user_name
        self.fs_zip_path = fs_zip_path

        # Загружаем структуру архива в память
        self.fs_structure = self.load_zip_structure(fs_zip_path)
        self.current_path = []  # путь от корня в виде списка директорий
        # root - словарь, в котором ключи - имена элементов, значения - либо dict (каталог) либо ('file', содержимое)
        # пример: {'dir1': {'subfile.txt': ('file', b'...')}, 'file2.txt': ('file', b'...')}

    def load_zip_structure(self, zip_path):
        structure = {}
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                # info.filename - полный путь внутри архива
                parts = info.filename.strip('/').split('/')
                # Пройдем по частям пути и создадим словари для директорий
                current_dir = structure
                for i, part in enumerate(parts):
                    if i == len(parts)-1:
                        # последний элемент - либо файл, либо пустой каталог
                        if info.is_dir():
                            # Каталог
                            if part not in current_dir:
                                current_dir[part] = {}
                        else:
                            # Файл - прочитаем его содержимое
                            with zf.open(info, 'r') as f:
                                content = f.read()
                            current_dir[part] = ('file', content)
                    else:
                        # промежуточный элемент - каталог
                        if part not in current_dir:
                            current_dir[part] = {}
                        current_dir = current_dir[part]

        return structure

    def get_prompt(self):
        if not self.current_path:
            rel_path = "/"
        else:
            rel_path = "/" + "/".join(self.current_path)
        return f"{self.user_name}@virtfs:{rel_path}$ "

    def ls_command(self):
        current_dir = self.get_current_dir()
        if isinstance(current_dir, dict):
            entries = list(current_dir.keys())
            entries.sort()
            return "\n".join(entries) if entries else ""
        return "Ошибка: текущий каталог не найден"

    def cd_command(self, path):
        new_path = self.resolve_path(path)
        if new_path is None:
            return f"Нет такого каталога: {path}"
        # Проверим, что это каталог
        target_dir = self.get_dir_by_path(new_path)
        if not isinstance(target_dir, dict):
            return f"Не является каталогом: {path}"
        self.current_path = new_path
        return ""

    def pwd_command(self):
        if not self.current_path:
            return "/"
        else:
            return "/" + "/".join(self.current_path)

    def mv_command(self, src, dst):
        src_path = self.resolve_path(src)
        if src_path is None:
            return f"Нет такого файла или директории: {src}"

        # Получим родительский каталог и имя перемещаемого элемента
        src_parent_path = src_path[:-1]
        src_name = src_path[-1]
        src_parent = self.get_dir_by_path(src_parent_path)
        if src_name not in src_parent:
            return f"Нет такого файла или директории: {src}"
        
        element = src_parent[src_name]

        # Определим целевой путь
        dst_path = self.resolve_path(dst, create_if_needed=True)
        if dst_path is None:
            return f"Некорректный путь назначения: {dst}"

        # Если целевой путь - каталог, переместим туда
        dst_parent_path = dst_path
        dst_parent = self.get_dir_by_path(dst_parent_path)

        # Если конечная точка указана как существующий файл/каталог?
        # Если dst указывает на существующий каталог, помещаем внутрь
        # Если dst указывает на несуществующий путь, это новое имя
        if isinstance(dst_parent, dict):
            # dst путь - это каталог (или новое имя внутри этого каталога)
            # Проверим, если последний компонент пути совпадает с именем src, тогда переименовать не нужно
            if self.path_is_directory(dst):
                # просто перемещаем элемент внутрь каталога dst_parent
                new_name = os.path.basename(src)
                # Если нужно новое имя, см. случаи:
                # Если пользователь указал dst как каталог, то имя остается прежним
                final_name = src_name
            else:
                # Пользователь указал путь, который не существует
                # Это будет новое имя элемента
                final_name = dst_path[-1]
                # тогда dst_parent_path - это родитель, dst_path[-1] - новый элемент
                dst_parent_path = dst_parent_path[:-1]
                dst_parent = self.get_dir_by_path(dst_parent_path)
                if dst_parent is None:
                    return f"Путь назначения не является каталогом: {os.path.dirname(dst)}"

            # Удаляем из старого места
            del src_parent[src_name]

            # Если был случай, что пользователь указал несуществующий путь c несколькими уровнями?
            # Мы выше это не разрешили, т.к. resolve_path(create_if_needed=True) не создаем многоуровневых директорий
            # Предполагается, что конечный каталог уже есть.

            # Добавляем в новый каталог
            if not self.path_is_directory(dst):
                # Это значит, что dst – путь к новому названию файла/каталога
                dst_parent[final_name] = element
            else:
                # Если dst - каталог, просто перемещаем с прежним именем
                dst_parent[src_name] = element

            return ""
        else:
            return f"Путь назначения не является каталогом: {dst}"

    def exit_command(self):
        # Здесь можно было бы переписать zip, если нужно.
        return "EXIT"

    def resolve_path(self, path, create_if_needed=False):
        # Разрешаем путь относительно current_path
        # Абсолютный путь начинается с /
        if path.startswith("/"):
            parts = [p for p in path.strip("/").split("/") if p]
            new_path = parts
        else:
            # относительный путь
            parts = path.split("/")
            new_path = self.current_path[:]
            for p in parts:
                if p == "" or p == ".":
                    continue
                elif p == "..":
                    if new_path:
                        new_path.pop()
                    # если пусто - остаёмся в корне
                else:
                    new_path.append(p)

        # Проверим, что путь существует (если не create_if_needed)
        dir_ref = self.get_dir_by_path(new_path, must_exist=not create_if_needed)
        if dir_ref is None and not create_if_needed:
            return None
        return new_path

    def get_dir_by_path(self, path_list, must_exist=True):
        # Идём по self.fs_structure
        current = self.fs_structure
        for i, p in enumerate(path_list):
            if not isinstance(current, dict):
                # не можем идти глубже, а нам надо
                return None
            if p not in current:
                if must_exist:
                    return None
                else:
                    # create_if_needed не реализован для многоуровневого
                    return None
            current = current[p]

        return current

    def path_is_directory(self, path):
        dir_ref = self.get_dir_by_path(path)
        return isinstance(dir_ref, dict)

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
