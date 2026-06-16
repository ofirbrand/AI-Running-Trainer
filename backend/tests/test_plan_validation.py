"""Tests for the strict AgentPlan validation schema."""
import pytest
from pydantic import ValidationError

from app.schemas import AgentPlan


def test_valid_plan():
    plan = AgentPlan.model_validate(
        {
            "structure_explanation": "x",
            "full_explanation": "y",
            "weeks": [
                {
                    "week_no": 1,
                    "workouts": [
                        {"weekday": 0, "workout_type": "Easy", "goal": "5k"},
                    ],
                }
            ],
        }
    )
    assert plan.weeks[0].workouts[0].weekday == 0


def test_rejects_empty_weeks():
    with pytest.raises(ValidationError):
        AgentPlan.model_validate(
            {"structure_explanation": "x", "full_explanation": "y", "weeks": []}
        )


def test_rejects_bad_weekday():
    with pytest.raises(ValidationError):
        AgentPlan.model_validate(
            {
                "structure_explanation": "x",
                "full_explanation": "y",
                "weeks": [
                    {"week_no": 1, "workouts": [{"weekday": 9, "workout_type": "x", "goal": "y"}]}
                ],
            }
        )
