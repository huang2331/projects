from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    base_dir: Path = Path(__file__).resolve().parent.parent
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "100"))
    database_path: str = os.getenv("DATABASE_PATH", "data/voice_coach.db")
    whisper_model: str = os.getenv("WHISPER_MODEL", "base.en")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    @property
    def db_path(self) -> Path:
        path = Path(self.database_path)
        return path if path.is_absolute() else self.base_dir / path


settings = Settings()
