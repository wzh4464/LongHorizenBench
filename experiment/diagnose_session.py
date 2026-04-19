#!/usr/bin/env python3
"""Diagnose Claude Code experiment sessions.

Usage:
    python3 experiment/diagnose_session.py <experiment_dir> [--json]

Output:
    - session_id
    - termination_cause: one of:
        - "unanswered_question"  — agent asked text questions (brainstorming trap), session ended with no implementation
        - "completed"            — agent used Edit/Write tools, finished normally
        - "empty_log"            — claude_run.jsonl is empty or missing
        - "crashed"              — session ended unexpectedly
    - last_assistant_text: preview of final assistant message
    - tool_summary: count of each tool used
"""

import json
import os
import sys
import re
from collections import Counter


def diagnose(exp_dir: str) -> dict:
    jsonl_path = os.path.join(exp_dir, "claude_run.jsonl")
    result = {
        "experiment": os.path.basename(os.path.normpath(exp_dir)),
        "session_id": None,
        "termination_cause": "unknown",
        "last_assistant_text": "",
        "tool_summary": {},
        "has_edit": False,
        "total_turns": 0,
        "details": [],
    }

    if not os.path.exists(jsonl_path) or os.path.getsize(jsonl_path) == 0:
        result["termination_cause"] = "empty_log"
        return result

    with open(jsonl_path) as f:
        lines = f.readlines()

    if not lines:
        result["termination_cause"] = "empty_log"
        return result

    # Parse all lines
    parsed = []
    for i, line in enumerate(lines):
        try:
            parsed.append((i, json.loads(line.strip())))
        except json.JSONDecodeError:
            pass

    # Extract session_id from first line that has one
    for i, obj in parsed:
        sid = obj.get("session_id", "")
        if sid:
            result["session_id"] = sid
            break

    # Count tools and find key events
    tool_counts = Counter()
    assistant_texts = []  # (line_idx, text)
    assistant_tool_uses = []  # (line_idx, tool_name)
    result_line = None
    used_ask_user = False
    used_brainstorming = False

    for i, obj in parsed:
        t = obj.get("type", "")
        msg = obj.get("message", {})

        if t == "result":
            result_line = (i, obj)

        if not msg:
            continue

        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "assistant":
            result["total_turns"] += 1
            if isinstance(content, list):
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    ct = c.get("type", "")
                    if ct == "text" and c.get("text", "").strip():
                        assistant_texts.append((i, c["text"]))
                    elif ct == "tool_use":
                        name = c.get("name", "")
                        tool_counts[name] += 1
                        assistant_tool_uses.append((i, name))
                        if name == "AskUserQuestion":
                            used_ask_user = True

    # Detect brainstorming skill invocation
    for i, obj in parsed:
        msg = obj.get("message", {})
        if not msg:
            continue
        content = msg.get("content", "")
        if isinstance(content, str) and "brainstorming" in content.lower():
            used_brainstorming = True
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict):
                    txt = c.get("text", "")
                    if "brainstorming" in txt.lower():
                        used_brainstorming = True

    # Also check Skill tool calls for brainstorming
    for i, obj in parsed:
        msg = obj.get("message", {})
        if not msg or msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Skill":
                    skill_input = c.get("input", {})
                    skill_name = skill_input.get("skill", "")
                    if "brainstorm" in skill_name.lower():
                        used_brainstorming = True

    result["tool_summary"] = dict(tool_counts.most_common())
    result["has_edit"] = "Edit" in tool_counts or "Write" in tool_counts

    # Get last assistant text
    if assistant_texts:
        last_idx, last_text = assistant_texts[-1]
        result["last_assistant_text"] = last_text[:500]

    # Determine termination cause
    has_result = result_line is not None
    result_subtype = result_line[1].get("subtype", "") if result_line else ""

    if not assistant_texts and not assistant_tool_uses:
        result["termination_cause"] = "empty_log"
    elif result["has_edit"]:
        # Agent actually wrote code
        result["termination_cause"] = "completed"
    elif not assistant_tool_uses:
        # Only text, no tools
        result["termination_cause"] = "unanswered_question"
        result["details"].append("Agent output text only, no tool calls in final turn")
    else:
        # Has tool uses but no Edit/Write — check if last message was a question
        last_text_line_idx = assistant_texts[-1][0] if assistant_texts else -1
        last_tool_line_idx = assistant_tool_uses[-1][0] if assistant_tool_uses else -1

        # Check: did the last assistant message end with text (question) or tool_use?
        # Find the last assistant message's content
        last_asst_idx = -1
        last_asst_content = None
        for i, obj in reversed(parsed):
            msg = obj.get("message", {})
            if msg and msg.get("role") == "assistant":
                last_asst_idx = i
                last_asst_content = msg.get("content", [])
                break

        if last_asst_content and isinstance(last_asst_content, list):
            last_items = [(c.get("type", ""), c) for c in last_asst_content if isinstance(c, dict)]
            last_types = [t for t, _ in last_items]

            # If last assistant message ends with text (no tool_use), it's likely a question
            # Strip thinking blocks
            non_thinking = [(t, c) for t, c in last_items if t != "thinking"]

            if non_thinking and non_thinking[-1][0] == "text":
                last_text_content = non_thinking[-1][1].get("text", "")
                # Heuristic: check for question marks or brainstorming patterns
                question_indicators = (
                    "?" in last_text_content
                    or "问题" in last_text_content
                    or "请" in last_text_content
                    or "how should" in last_text_content.lower()
                    or "what should" in last_text_content.lower()
                    or "would you" in last_text_content.lower()
                    or "please clarify" in last_text_content.lower()
                )
                if question_indicators:
                    result["termination_cause"] = "unanswered_question"
                    result["details"].append(
                        "Last assistant message is text with question indicators, "
                        "session ended immediately after (no user response)"
                    )
                elif used_brainstorming and not result["has_edit"]:
                    result["termination_cause"] = "unanswered_question"
                    result["details"].append(
                        "Brainstorming skill was used, agent asked text questions "
                        "that were never answered"
                    )
                else:
                    result["termination_cause"] = "completed_no_edit"
                    result["details"].append(
                        "Agent finished but made no file edits"
                    )
            elif non_thinking and non_thinking[-1][0] == "tool_use":
                last_tool_name = non_thinking[-1][1].get("name", "")
                if last_tool_name in ("TodoWrite",):
                    # TodoWrite without subsequent Edit = stuck in planning
                    result["termination_cause"] = "unanswered_question"
                    result["details"].append(
                        f"Last tool was {last_tool_name} (planning), "
                        "no implementation followed"
                    )
                else:
                    result["termination_cause"] = "completed_no_edit"
                    result["details"].append(
                        f"Last tool was {last_tool_name}, but no Edit/Write used"
                    )
            else:
                result["termination_cause"] = "completed_no_edit"
        else:
            result["termination_cause"] = "completed_no_edit"

    # Add brainstorming flag to details
    if used_brainstorming:
        result["details"].insert(0, f"Brainstorming skill invoked: {used_brainstorming}")
    if used_ask_user:
        result["details"].insert(0, f"AskUserQuestion tool used: {used_ask_user}")

    return result


def format_report(result: dict) -> str:
    lines = []
    lines.append(f"=== Session Diagnosis: {result['experiment']} ===")
    lines.append(f"Session ID:  {result['session_id'] or 'N/A'}")
    lines.append(f"Termination: {result['termination_cause']}")
    lines.append(f"Total turns: {result['total_turns']}")
    lines.append(f"Has edits:   {result['has_edit']}")
    lines.append("")
    lines.append("Tool summary:")
    for name, count in sorted(result["tool_summary"].items(), key=lambda x: -x[1]):
        lines.append(f"  {name}: {count}")
    if result["details"]:
        lines.append("")
        lines.append("Details:")
        for d in result["details"]:
            lines.append(f"  - {d}")
    if result["last_assistant_text"]:
        lines.append("")
        lines.append(f"Last assistant text (500 chars):")
        lines.append(f"  {result['last_assistant_text'][:500]}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    exp_dir = sys.argv[1]
    output_json = "--json" in sys.argv

    result = diagnose(exp_dir)

    if output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
        # Suggest how to resume if unanswered_question
        if result["termination_cause"] == "unanswered_question" and result["session_id"]:
            print("")
            print(f"To resume: claude --resume {result['session_id']}")
