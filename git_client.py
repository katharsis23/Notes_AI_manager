import pathlib
import subprocess

from rich.console import Console

console = Console()

class GitClient:
    """Git client for local storing"""

    def __init__(self, vault_path: pathlib.Path):
        self.vault_path = vault_path

    def _run_git(self, args: list[str]) -> tuple[bool, str]:
        """Helper for executing git commands"""
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
            return False, "Git CLI is not installed"

    def is_git_repo(self) -> bool:
        """Checking the Vault dir for git repos"""
        ok, _ = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return ok

    def commit_and_push(self, file_path: pathlib.Path, commit_message: str) -> bool:
        """Indexing file -> commit -> push"""
        if not self.is_git_repo():
            console.print("[yellow]Vault is not a Git repository. Skipping.[/yellow]")
            return False

        # Get relative file path
        try:
            rel_path = file_path.relative_to(self.vault_path)
        except ValueError:
            rel_path = file_path

        # 1. git add
        ok, err = self._run_git(["add", str(rel_path)])
        if not ok:
            console.print(f"[bold red]Git add error:[/bold red] {err}")
            return False

        # 2. git commit
        ok, out = self._run_git(["commit", "-m", commit_message])
        if not ok:
            # In case of no changes
            if "nothing to commit" in err or "nothing to commit" in out:
                console.print("[yellow]Git: no changes.[/yellow]")
                return True
            console.print(f"[bold red]Git commit error:[/bold red] {err}")
            return False

        console.print(f"[bold green]✔ Git commit success:[/bold green] {commit_message}")

        # 3. git push
        ok, err = self._run_git(["push"])
        if not ok:
            console.print(f"[bold yellow]⚠ Git push failed (Check network or remote):[/bold yellow] {err}")
            return False

        console.print("[bold green]✔ Git push success![/bold green]")
        return True
