import httpx as http
from rich.console import Console

console = Console()


class OllamaClient:

    def __init__(
        self,
        url: str,
        model_name: str,
        num_ctx: int = 4096,
        num_predict: int = 2560,
    ):
        self.url = url
        self.model_name = model_name
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    async def query(
        self,
        prompt: str,
        is_json: bool = True,
        temperature: float = 0.3,
    ) -> str:

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }

        if is_json:
            payload["format"] = "json"

        console.print("\n[bold magenta]\u2501\u2501\u2501 Ollama Request \u2501\u2501\u2501[/bold magenta]")
        console.print(f"  Model:        [yellow]{self.model_name}[/yellow]")
        console.print(f"  URL:          [yellow]{self.url}[/yellow]")
        console.print(f"  JSON mode:    {is_json}")
        console.print(f"  Temperature:  {temperature}")
        console.print(f"  Context:      {self.num_ctx}")
        console.print(f"  Max tokens:   {self.num_predict}")
        console.print(f"  Prompt chars: {len(prompt)}")
        console.print(f"  Prompt words: {len(prompt.split())}")
        console.print(
            f"  Prompt preview:\n"
            f"[dim]{prompt[:1000]}[/dim]"
        )

        timeout_config = http.Timeout(
            600.0,
            connect=15.0,
        )

        try:
            async with http.AsyncClient(
                timeout=timeout_config
            ) as client:

                response = await client.post(
                    url=self.url,
                    json=payload,
                )

                console.print(
                    f"  HTTP status: [yellow]{response.status_code}[/yellow]"
                )

                if response.status_code >= 400:
                    console.print(
                        "[bold red]\u2501\u2501\u2501 Ollama Error Response \u2501\u2501\u2501[/bold red]"
                    )
                    console.print(response.text)

                    console.print(
                        "[bold red]\u2501\u2501\u2501 Request Payload \u2501\u2501\u2501[/bold red]"
                    )
                    console.print(payload)

                response.raise_for_status()

                response_data = response.json()

                console.print(
                    f"  Response keys: {list(response_data.keys())}"
                )

                result = response_data.get("response", "")

                console.print(
                    f"  Response chars: {len(result)}"
                )

                console.print(
                    f"  Response preview:\n"
                    f"[dim]{result[:1000]}[/dim]"
                )

                console.print(
                    "[bold green]\u2714 Ollama request completed[/bold green]"
                )

                return result

        except http.HTTPStatusError:
            console.print(
                "[bold red]\u2718 Ollama HTTP request failed[/bold red]"
            )
            raise

        except Exception as e:
            console.print(
                f"[bold red]\u2718 Ollama client error: "
                f"{type(e).__name__}: {e}[/bold red]"
            )
            raise