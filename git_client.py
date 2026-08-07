import subprocess
import pathlib
from rich.console import Console

console = Console()

class GitClient:
    """Модуль для роботи з Git у локальному Obsidian Vault."""

    def __init__(self, vault_path: pathlib.Path):
        self.vault_path = vault_path

    def _run_git(self, args: list[str]) -> tuple[bool, str]:
        """Допоміжний метод для виконання системних git-команд."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.vault_path,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()
        except FileNotFoundError:
            return False, "Git CLI не встановлено в системі."

    def is_git_repo(self) -> bool:
        """Перевіряє, чи є Vault git-репозиторієм."""
        ok, _ = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return ok

    def commit_and_push(self, file_path: pathlib.Path, commit_message: str) -> bool:
        """Індексує файл, робить коміт та push у віддалений репозиторій."""
        if not self.is_git_repo():
            console.print("[yellow]Vault не є Git-репозиторієм. Пропускаємо коміт.[/yellow]")
            return False

        # Отримуємо відносний шлях файлу від кореня Vault
        try:
            rel_path = file_path.relative_to(self.vault_path)
        except ValueError:
            rel_path = file_path

        # 1. git add
        ok, err = self._run_git(["add", str(rel_path)])
        if not ok:
            console.print(f"[bold red]Git add помилка:[/bold red] {err}")
            return False

        # 2. git commit
        ok, out = self._run_git(["commit", "-m", commit_message])
        if not ok:
            # Якщо немає змін для коміту (наприклад, файл не змінився)
            if "nothing to commit" in err or "nothing to commit" in out:
                console.print("[yellow]Git: немає нових змін для коміту.[/yellow]")
                return True
            console.print(f"[bold red]Git commit помилка:[/bold red] {err}")
            return False

        console.print(f"[bold green]✔ Git commit успішний:[/bold green] {commit_message}")

        # 3. git push
        ok, err = self._run_git(["push"])
        if not ok:
            console.print(f"[bold yellow]⚠ Git push не вдався (можливо, відсутній remote або мережа):[/bold yellow] {err}")
            return False

        console.print("[bold green]✔ Зміни успішно відправлені в хмару (git push)![/bold green]")
        return True