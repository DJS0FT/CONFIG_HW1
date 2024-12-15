import unittest
import os
import shutil
import tempfile
import zipfile
from emulator import ShellEmulator

class TestShellEmulator(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию и zip-архив для тестов
        self.test_dir = tempfile.mkdtemp()
        self.root_dir = os.path.join(self.test_dir, "root")
        os.mkdir(self.root_dir)
        # Создаем пример файловой структуры
        with open(os.path.join(self.root_dir, "file1.txt"), "w") as f:
            f.write("Hello")
        os.mkdir(os.path.join(self.root_dir, "folder1"))
        with open(os.path.join(self.root_dir, "folder1", "file2.txt"), "w") as f:
            f.write("Inside folder1")
        os.mkdir(os.path.join(self.root_dir, "folder2"))

        # Создаем zip
        self.zip_path = os.path.join(self.test_dir, "test_fs.zip")
        with zipfile.ZipFile(self.zip_path, 'w') as zf:
            for root, dirs, files in os.walk(self.test_dir):
                for file in files:
                    if file != "test_fs.zip":
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, self.test_dir)
                        zf.write(full_path, arcname)

        self.emulator = ShellEmulator("testuser", self.zip_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # Тесты для ls
    def test_ls_root_contents(self):
        result = self.emulator.run_command("ls")
        self.assertIn("file1.txt", result)
        self.assertIn("folder1", result)
        self.assertIn("folder2", result)

    def test_ls_folder(self):
        self.emulator.run_command("cd folder1")
        result = self.emulator.run_command("ls")
        self.assertIn("file2.txt", result)

    def test_ls_empty_dir(self):
        empty_dir = os.path.join(self.root_dir, "emptydir")
        os.mkdir(empty_dir)
        self.emulator.run_command("cd emptydir")
        result = self.emulator.run_command("ls")
        self.assertEqual(result, "")

    # Тесты для cd
    def test_cd_valid_dir(self):
        result = self.emulator.run_command("cd folder1")
        self.assertEqual(result, "")
        self.assertEqual(self.emulator.pwd_command(), "/folder1")

    def test_cd_invalid_dir(self):
        result = self.emulator.run_command("cd no_such_dir")
        self.assertIn("Нет такого каталога", result)

    def test_cd_root(self):
        self.emulator.run_command("cd folder1")
        result = self.emulator.run_command("cd /")
        self.assertEqual(result, "")
        self.assertEqual(self.emulator.pwd_command(), "/")

    def test_cd_parent(self):
        self.emulator.run_command("cd folder1")
        result = self.emulator.run_command("cd ..")
        self.assertEqual(result, "")
        self.assertEqual(self.emulator.pwd_command(), "/")

    def test_cd_parent_at_root(self):
        result = self.emulator.run_command("cd ..")
        self.assertIn("Нет такого каталога", result)
        self.assertEqual(self.emulator.pwd_command(), "/")

    # Тесты для pwd
    def test_pwd_root(self):
        result = self.emulator.run_command("pwd")
        self.assertEqual(result, "/")

    def test_pwd_subdir(self):
        self.emulator.run_command("cd folder1")
        result = self.emulator.run_command("pwd")
        self.assertEqual(result, "/folder1")

    def test_pwd_nested_dir(self):
        os.mkdir(os.path.join(self.root_dir, "folder1", "subfolder"))
        self.emulator.run_command("cd folder1/subfolder")
        result = self.emulator.run_command("pwd")
        self.assertEqual(result, "/folder1/subfolder")

    # Тесты для mv
    def test_mv_rename_file(self):
        result = self.emulator.run_command("mv file1.txt file1_renamed.txt")
        self.assertEqual(result, "")
        ls_result = self.emulator.run_command("ls")
        self.assertIn("file1_renamed.txt", ls_result)
        self.assertNotIn("file1.txt", ls_result)

    def test_mv_move_file_to_dir(self):
        result = self.emulator.run_command("mv file1.txt folder1")
        self.assertEqual(result, "")
        self.emulator.run_command("cd folder1")
        ls_result = self.emulator.run_command("ls")
        self.assertIn("file1.txt", ls_result)

    def test_mv_nonexistent_source(self):
        result = self.emulator.run_command("mv nofile.txt newname.txt")
        self.assertIn("Нет такого файла или директории", result)

    def test_mv_invalid_destination(self):
        result = self.emulator.run_command("mv file1.txt /no_such_dir/")
        self.assertIn("Некорректный путь назначения", result)

    # Тесты для exit
    def test_exit_command(self):
        result = self.emulator.run_command("exit")
        self.assertEqual(result, "EXIT")

    def test_exit_after_commands(self):
        self.emulator.run_command("ls")
        result = self.emulator.run_command("exit")
        self.assertEqual(result, "EXIT")

    def test_exit_twice(self):
        self.emulator.run_command("exit")
        # Повторный вызов exit уже не имеет смысла, но проверим что не будет ошибки
        result = self.emulator.run_command("exit")
        # Так как после первого exit временная директория удалена, ожидание ошибки
        self.assertIn("Нет такого каталога", result)

if __name__ == '__main__':
    unittest.main()
