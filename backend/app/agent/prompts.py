"""Prompt construction for the running-coach agent."""
from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are an elite private running coach. You design safe, \
individualized, periodized plans built from THIS athlete's data, never generic \
templates.

COACHING PRINCIPLES
- Derive every decision (volume, paces, HR zones, workout choice) from the \
athlete's current fitness, recent load, history, and goal. Set paces/zones from \
their most relevant benchmark (recent race, time trial, or threshold data); never \
assume fitness they have not demonstrated. When data is thin or conflicting, choose \
the conservative option and say so.
- Periodize toward the target date (base, build, peak, taper) with a recovery week \
roughly every 3rd-4th week. Progress volume gradually (about 10% per week at most); \
never spike load after a down week or missed training.
- Use an easy/hard split: most volume is easy aerobic running, with limited, \
purposeful quality (threshold, VO2, intervals, race-pace). Easy days stay easy and \
hard days stay hard. Quality over quantity.
- Match structure to the goal: 5K, half, marathon, first race, or general fitness \
each need a different emphasis (speed vs. endurance vs. durability).
- Protect the athlete: honor injury history and schedule real recovery. If the goal \
is unrealistic for the timeline or fitness, build the most ambitious SAFE plan and \
flag the gap rather than overreach.

CONSTRAINTS
- Respect available training days, time per session, preferred long-run day, \
equipment, and constraints (other sports, strength, travel, vacations, injuries).
- Use the athlete's own units and pace format, and reference their data when it \
explains a choice.
- The week starts on SUNDAY. Weekday indices: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, \
5=Fri, 6=Sat.

WORKOUTS
- Every session has a specific, measurable goal (distance or duration, target \
pace/effort/HR) plus concise how-to guidance, including warm-up and cool-down for \
quality sessions.
- Provide a short list of the workout TYPES used, each with a one-sentence, \
tooltip-friendly description.

OUTPUT
- Return the FINAL plan by calling `submit_plan` exactly once; never leave it only \
in prose. The plan must cover every week from week 1 through the final taper into \
the target date.
"""


REASONING_GUIDANCE = {
    "minimal": "Keep reasoning brief and produce the plan efficiently.",
    "low": "Do a light review of the athlete's data before planning.",
    "medium": "Carefully consider the athlete's data, history, and goal before planning.",
    "high": "Reason deeply and methodically about periodization, the athlete's "
    "strengths and weaknesses, recovery, and risk before producing the plan.",
}


def _section(title: str, body: Any) -> str:
    if isinstance(body, (dict, list)):
        body = json.dumps(body, indent=2, default=str)
    return f"## {title}\n{body}\n"


def reasoning_line(effort: str) -> str:
    return REASONING_GUIDANCE.get(effort, REASONING_GUIDANCE["medium"])


def build_generate_prompt(context: dict[str, Any]) -> str:
    """Prompt for a brand-new plan."""
    parts = [
        "Create a complete running training plan for this athlete.",
        "",
        _section("Athlete profile", context.get("profile", {})),
        _section("Fitness & health metrics", context.get("metrics", {})),
    ]
    activities = context.get("activities") or []
    if activities:
        parts.append(
            _section("Recent Garmin activity history (most recent first)", activities)
        )
        parts.append(
            "The athlete chose to include the activity history above. Use it to gauge "
            "current fitness, typical weekly volume, recent long-run distance, paces, and "
            "training consistency, and calibrate the plan's starting load and progression "
            "accordingly.\n"
        )
    parts.extend(
        [
            _section("Plan request", context.get("inputs", {})),
            _section(
                "Calendar",
                {
                    "start_date_sunday": context.get("start_date"),
                    "num_weeks": context.get("num_weeks"),
                    "target_date": context.get("target_date"),
                    "note": "Week 1 begins on start_date_sunday. Produce exactly "
                    f"{context.get('num_weeks')} weeks.",
                },
            ),
            "",
            "When ready, call `submit_plan` with the full structured plan.",
        ]
    )
    return "\n".join(parts)


def build_chat_edit_prompt(context: dict[str, Any]) -> str:
    """Prompt for regenerating a plan after the user requests changes in chat."""
    parts = [
        "The athlete reviewed the plan below and requested changes. Produce a new "
        "version that honors the requested changes. The requested changes OVERRIDE "
        "the original inputs where they conflict. In `change_summary`, explain what "
        "changed versus the previous version and why.",
        "",
        _section("Athlete profile", context.get("profile", {})),
        _section("Fitness & health metrics", context.get("metrics", {})),
        _section("Original plan request", context.get("inputs", {})),
        _section("Current plan (to be revised)", context.get("current_plan", {})),
        _section("Requested changes", context.get("change_requests", [])),
        _section(
            "Calendar",
            {
                "start_date_sunday": context.get("start_date"),
                "num_weeks": context.get("num_weeks"),
                "target_date": context.get("target_date"),
            },
        ),
        "",
        "When ready, call `submit_plan` with the full revised plan.",
    ]
    return "\n".join(parts)


def build_weekly_update_prompt(context: dict[str, Any]) -> str:
    """Prompt for the end-of-week review of completed vs planned work."""
    parts = [
        "Review the athlete's progress against the active plan. Decide whether the "
        "plan should be updated to better reach the goal (e.g. adjust load, target "
        "weaknesses, improve workout quality, or re-balance after missed sessions). "
        "If an update is warranted, produce a full revised plan for the REMAINING "
        "weeks (keep already-completed weeks unchanged) and explain what changed and "
        "why in `change_summary`. If no change is needed, set change_summary to "
        "exactly 'NO_CHANGE_NEEDED' and still return the current plan unchanged.",
        "",
        _section("Athlete profile", context.get("profile", {})),
        _section("Fitness & health metrics", context.get("metrics", {})),
        _section("Original plan request", context.get("inputs", {})),
        _section("Current active plan", context.get("current_plan", {})),
        _section("Progress so far (planned vs actual)", context.get("progress", {})),
        _section(
            "Calendar",
            {
                "start_date_sunday": context.get("start_date"),
                "num_weeks": context.get("num_weeks"),
                "target_date": context.get("target_date"),
                "current_week": context.get("current_week"),
            },
        ),
        "",
        "When ready, call `submit_plan` with the plan (revised or unchanged).",
    ]
    return "\n".join(parts)


def build_manual_update_prompt(context: dict[str, Any]) -> str:
    """Prompt for a user-described manual change to the plan."""
    parts = [
        "The athlete wants to change the plan as described below. Update the plan "
        "accordingly, reviewing the original plan together with the new requirements "
        "(e.g. new deadline, new goal, different available days, a vacation period, "
        "etc.). Keep already-completed weeks unchanged where possible. Explain what "
        "changed and why in `change_summary`.",
        "",
        _section("Athlete profile", context.get("profile", {})),
        _section("Fitness & health metrics", context.get("metrics", {})),
        _section("Original plan request", context.get("inputs", {})),
        _section("Current active plan", context.get("current_plan", {})),
        _section("Requested change", context.get("request_text", "")),
        _section(
            "Calendar",
            {
                "start_date_sunday": context.get("start_date"),
                "num_weeks": context.get("num_weeks"),
                "target_date": context.get("target_date"),
                "current_week": context.get("current_week"),
            },
        ),
        "",
        "When ready, call `submit_plan` with the full revised plan.",
    ]
    return "\n".join(parts)
