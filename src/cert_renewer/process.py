import subprocess
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessError(RuntimeError):
    pass


class ProcessRunner:
    def run(self, argv: Sequence[str], *, input_text: str | None = None) -> ProcessResult:
        completed = subprocess.run(
            list(argv), input=input_text, text=True, capture_output=True,
            check=False, timeout=600,
        )
        result = ProcessResult(completed.returncode, completed.stdout, completed.stderr)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "command failed").strip()[-2000:]
            raise ProcessError(f"{argv[0]} failed: {message}")
        return result
