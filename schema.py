"""Output model. The agent must return JSON matching Strategy."""

from pydantic import BaseModel, Field


class StrategyActions(BaseModel):
    text: str = Field(description="The text of the strategy update, including the table, product and all headings")
    justification: str = Field(description="Justification for the strategy, including brand references and evidence from data files")


class Strategy(BaseModel):
    title: str = Field(description="Strategy title, e.g. 'Increase market share in segment X'")
    summary: str = Field(description="Two or three sentences on what changes and why")
    body: list[StrategyActions] = Field(description="Full description of the strategy, including plan, budget, expected result")

    def to_markdown(self) -> str:
        """The whole strategy as one Markdown document."""
        parts = [f"# {self.title}", self.summary]
        for item in self.body:
            parts += [item.text.strip(), "**Justification**", item.justification.strip()]
        return "\n\n".join(parts) + "\n"
