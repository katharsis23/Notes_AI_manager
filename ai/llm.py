import httpx as http

class OllamaClient:
    def __init__(self, url: str, model_name: str):
        self.url = url
        self.model_name = model_name

    async def query(self, prompt: str, is_json: bool = True, temperature: float = 0.3) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,        # Зменшено з 8192 для істотного прискорення prefill
                "num_predict": 2560
            }
        }
        if is_json:
            payload["format"] = "json"

        # Налаштовуємо окремі таймаути: connect — швидко, read — розширено
        timeout_config = http.Timeout(600.0, connect=15.0)

        async with http.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(url=self.url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "")