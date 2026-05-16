from .http import HttpClient
from .models import ModelRegistry
from .training import TrainingClient
from .datasets import DatasetClient
from .benchmark import BenchmarkClient
from .inference import InferenceClient
from .projects import ProjectsClient
from .auth import load_token, save_token, delete_token

class MLForge:
    def __init__(
        self,
        host: str = "http://127.0.0.1",
        port: int = 8005,
        token: str | None = None,
        api_key: str | None = None,
    ):
        # Default to local engine. Cloud registry is now curated via Gateway.
        if "://" in host:
            self.base_url = host.rstrip("/")
        else:
            self.base_url = f"http://{host}:{port}"
            
        # If the user provided a URL with a protocol but no port, and specified a custom port, append it
        if "://" in self.base_url and ":" not in self.base_url.split("://")[1] and port:
             # Only append if not standard 80/443 or if explicitly different from default 8005
             if port != 80 and port != 443:
                 self.base_url = f"{self.base_url}:{port}"

        effective_token = token or load_token()
        self.http = HttpClient(self.base_url, token=effective_token, api_key=api_key)

        # Backward-compatible clients
        self.models = ModelRegistry(self.http)
        self.train = TrainingClient(self.http)
        self.datasets = DatasetClient(self.http)
        self.benchmark = BenchmarkClient(self.http)
        self.inference = InferenceClient(self.http)

        # New: projects client
        self.projects = ProjectsClient(self.http)
