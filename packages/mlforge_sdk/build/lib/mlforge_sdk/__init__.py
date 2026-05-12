from .http import HttpClient
from .models import ModelRegistry
from .training import TrainingClient
from .datasets import DatasetClient
from .benchmark import BenchmarkClient
from .inference import InferenceClient
from .projects import ProjectsClient
from .auth import load_token

class MLForge:
    def __init__(
        self,
        host: str = "https://senthil2421-mlforge.hf.space",
        port: int = 7860,
        token: str | None = None,
    ):
        # Hugging Face Spaces internal port is 7860, external is 443 (HTTPS)
        # If the user provides a full https URL, we use it directly.
        if host.startswith("https"):
            self.base_url = host.rstrip("/")
        else:
            self.base_url = f"{host}:{port}"
        # For public registry, token is optional. If no token is provided or found, requests are anonymous.
        effective_token = token or load_token()
        self.http = HttpClient(self.base_url, token=effective_token)

        # Backward-compatible clients
        self.models = ModelRegistry(self.http)
        self.train = TrainingClient(self.http)
        self.datasets = DatasetClient(self.http)
        self.benchmark = BenchmarkClient(self.http)
        self.inference = InferenceClient(self.http)

        # New: projects client
        self.projects = ProjectsClient(self.http)
