"""
models.py — structured request models for the trip agent.
"""

from datetime import date

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=1, description="City or place name.")
    start_date: date = Field(..., description="Trip start date.")
    end_date: date | None = Field(
        None, description="Trip end date. If omitted, treated as a single-day trip."
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Optional interests, e.g. ['hiking', 'food', 'history'].",
    )

    @field_validator("end_date")
    @classmethod
    def end_not_before_start(cls, v: date | None, info) -> date | None:
        start = info.data.get("start_date")
        if v is not None and start is not None and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v

    def to_question(self) -> str:
        """
        Render this structured request as a natural-language question for
        the agent. Explicitly including the ISO dates in the text (not just
        holding them as separate fields) is what lets the agent pick them up
        and pass matching start_date/end_date arguments when it calls
        get_weather — see tools/weather.py for the filtering that enables.
        """
        date_range = self.start_date.isoformat()
        if self.end_date and self.end_date != self.start_date:
            date_range += f" to {self.end_date.isoformat()}"

        parts = [f"I'm planning a trip to {self.destination} from {date_range}."]
        if self.interests:
            parts.append(f"I'm especially interested in: {', '.join(self.interests)}.")
        parts.append(
            "What should I know about weather and public holidays for these exact dates?"
        )
        return " ".join(parts)