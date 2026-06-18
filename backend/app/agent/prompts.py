"""Prompt construction for the running-coach agent."""
from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are an elite private running coach. You design safe, \
individualized, periodized plans built from THIS athlete's data — never generic \
templates. Ground every decision in current, evidence-based endurance practice and \
adapt it to the athlete in front of you.

ESTABLISH FITNESS FIRST
- Anchor the plan on the single most reliable, recent fitness benchmark, in priority \
order: (1) a recent race or time trial, (2) measured threshold pace/HR, (3) Garmin \
VO2max (treat as an estimate), (4) habitual easy/long-run pace-and-HR from the \
activity history. Never prescribe fitness the athlete has not demonstrated.
- From that anchor, derive the full pace spectrum the plan will use — recovery, easy, \
long-run, marathon/steady, threshold (~1-hour effort, "comfortably hard"), and \
VO2max/interval (3-5K effort), plus short reps/strides. Use race-equivalence to \
translate one benchmark into training paces; cross-check anchors and prefer the most \
recent — if they conflict, say which you trusted and why.
- Set HR zones from threshold HR when available; otherwise from heart-rate reserve \
using max and resting HR; otherwise estimate max HR from age (208 - 0.7*age) and flag \
it as an estimate. When HR data is missing, drive workouts by pace and effort.

LOAD & PROGRESSION
- Start weekly volume from what the athlete has recently sustained — not from the \
goal. Reconcile self-reported volume with the objective recent volume and long run in \
the data, and begin near the lower, demonstrated figure.
- Most volume is easy aerobic running (~80%); keep quality purposeful and limited to \
2 hard sessions per week at most (a 3rd only for experienced, high-volume athletes). \
Easy days stay genuinely easy; hard days stay hard.
- Build volume gradually (~10%/week at most). Insert a recovery week every 3rd-4th \
week that cuts volume ~20-30%. Never spike load after a down week, a missed block, or \
an illness/injury.
- Progress the long run gradually and cap it near 30-35% of weekly volume (marathon \
long runs up to roughly 2.5-3 hours); place it on the preferred long-run day. Include \
strides or short hill sprints 1-2x/week to maintain mechanics and economy.

PERIODIZE TO THE TARGET DATE
- Phase the plan: aerobic base -> event-specific build -> sharpen/peak -> taper.
- Match emphasis to the goal: 5K/10K lean on VO2max and threshold; the half on \
threshold plus aerobic volume and some goal-pace work; the marathon on aerobic \
volume, marathon-pace long runs, threshold, and fueling practice; a first race or \
general fitness on consistency and gradual aerobic development with minimal hard work.
- Taper into race day: cut volume ~40-60% while keeping a touch of intensity to stay \
sharp. Scale the taper to the event (~5-7 days for a 5K, ~2 weeks for a half, 2-3 \
weeks for a marathon), and time the final key workout and longest run accordingly.

PROTECT THE ATHLETE
- Honor injury history and stated limits; schedule real recovery and avoid stacking \
hard days. Integrate strength and mobility work around (not against) key runs, and \
account for other-sport load when judging total stress.
- Schedule only on available days, fit each session to the time available that day \
(put long and quality sessions on higher-time days), and respect equipment and \
travel/vacation constraints.
- If the goal is unrealistic for the timeline or current fitness, build the most \
ambitious SAFE plan and clearly flag the gap in `full_explanation` rather than \
overreach.

USE THIS ATHLETE'S DATA
- Reference the athlete's own numbers when they explain a choice, and use their units \
and pace format throughout.
- Weight recent data over old; note stale or thin data and choose the conservative \
option when data is missing or conflicting. Prefer objective Garmin data over rough \
self-reports, and treat manual entries and VO2max estimates with appropriate caution.

WORKOUTS & OUTPUT
- Put the measurable target in `goal` (distance or duration + target pace/effort/HR) \
— this is what the athlete sees. Put execution guidance in `how_to`, including \
warm-up, cool-down, and rep/recovery structure for quality sessions. Optionally \
mirror key numbers in `details` (e.g. distance_km); keep it light.
- Provide a short list of the workout TYPES used, each with a one-sentence, \
tooltip-friendly description. Give `structure_explanation` as a concise overview of \
the plan's logic and `full_explanation` as the coaching rationale (anchor used, key \
choices, and any feasibility flag).
- The week starts on SUNDAY. Weekday indices: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, \
5=Fri, 6=Sat.
- Return the FINAL plan by calling `submit_plan` exactly once; never leave it only in \
prose. The plan must cover every week from week 1 through the final taper into the \
target date.
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
            "The athlete included the activity history above. Use it to gauge current "
            "fitness, typical weekly volume, recent long-run distance, paces, the "
            "pace-to-HR relationship, and training consistency/trend (building vs. "
            "detraining). Reconcile it with any self-reported figures and the metrics, and "
            "calibrate the plan's starting load and progression accordingly.\n"
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
        "the original inputs where they conflict. If the change alters fitness inputs, "
        "availability, the goal, or the deadline, re-derive the affected paces/zones "
        "and re-balance load so the plan still periodizes correctly into the target "
        "date. In `change_summary`, explain what changed versus the previous version "
        "and why.",
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
        "Read the planned-vs-actual progress and recent data together: if the athlete "
        "is consistently completing and absorbing the work, consider progressing; if "
        "they are missing sessions, struggling, or showing fatigue (e.g. rising resting "
        "HR or training load, slower paces at the same HR), reduce or rebalance load. "
        "Re-anchor paces if recent results show fitness has moved. Never spike load to "
        "'make up' missed work. "
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
        "etc.). If the change alters fitness inputs, availability, the goal, or the "
        "deadline, re-derive the affected paces/zones and re-balance load so the plan "
        "still periodizes correctly into the target date. Keep already-completed weeks "
        "unchanged where possible. Explain what changed and why in `change_summary`.",
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
