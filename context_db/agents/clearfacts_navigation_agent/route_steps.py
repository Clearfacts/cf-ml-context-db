from __future__ import annotations

import re

from .schemas import (
    CredentialField,
    ExplorationActionType,
    NavigationOntologyDocument,
    NavigationPathObservation,
    NavigationRouteStep,
)


def parse_legacy_route_step(raw_step: str, *, source_base_url: str) -> NavigationRouteStep | None:
    step = raw_step.strip().strip("'\"")
    navigate_match = re.match(r"^(?:Navigate|Go) to\s+(.+)$", step, flags=re.IGNORECASE)
    if navigate_match:
        url = navigate_match.group(1).strip().strip("'\"")
        if url.startswith("/"):
            url = f"{source_base_url.rstrip('/')}{url}"
        return NavigationRouteStep(
            operation=ExplorationActionType.NAVIGATE_URL,
            instruction=step,
            url=url,
            expected_outcome=f"Browser navigates to {url}.",
        )

    credential_match = re.match(
        r"^Type\s+(?:valid\s+)?(username|password|gebruikersnaam|wachtwoord)\s+into\s+(.+)$",
        step,
        flags=re.IGNORECASE,
    )
    if credential_match:
        raw_field = credential_match.group(1).lower()
        field = CredentialField.PASSWORD if raw_field in {"password", "wachtwoord"} else CredentialField.USERNAME
        target = credential_match.group(2).strip().strip("`'\"")
        return NavigationRouteStep(
            operation=ExplorationActionType.TYPE_ROLE_CREDENTIAL,
            instruction=step,
            target=target,
            credential_field=field,
            expected_outcome=f"{field.value} is filled.",
        )

    click_match = re.match(r"^(?:On\s+.+?,\s*)?Click\s+(.+)$", step, flags=re.IGNORECASE)
    if click_match:
        target = _normalize_click_target(click_match.group(1).strip().strip("`'\""))
        return NavigationRouteStep(
            operation=ExplorationActionType.CLICK,
            instruction=step,
            target=target,
            expected_outcome="Browser responds to the click.",
        )
    return None


def typed_steps_for_navigation_path(
    path: NavigationPathObservation,
    *,
    source_base_url: str,
    include_success_wait: bool = True,
) -> list[NavigationRouteStep]:
    path_steps = list(path.typed_route_steps)
    if not path_steps:
        path_steps = [
            parsed
            for raw_step in path.route_steps
            if (parsed := parse_legacy_route_step(raw_step, source_base_url=source_base_url)) is not None
        ]

    if include_success_wait and path_steps and not any(
        step.operation == ExplorationActionType.WAIT_FOR_TEXT for step in path_steps
    ):
        wait_text = wait_text_from_success_criteria(path.success_criteria)
        if wait_text:
            path_steps.append(
                NavigationRouteStep(
                    operation=ExplorationActionType.WAIT_FOR_TEXT,
                    instruction=f"Wait until {path.to_screen or 'the target page'} is visible.",
                    text=wait_text,
                    expected_outcome=f"{wait_text} is visible.",
                )
            )
    return path_steps


def backfill_typed_route_steps(document: NavigationOntologyDocument, *, source_base_url: str | None = None) -> int:
    base_url = source_base_url or document.base_url
    added_count = 0
    for path in document.navigation_paths:
        if path.typed_route_steps:
            continue
        typed_steps = typed_steps_for_navigation_path(path, source_base_url=base_url)
        if typed_steps:
            path.typed_route_steps = typed_steps
            added_count += len(typed_steps)
    return added_count


def wait_text_from_success_criteria(success_criteria: list[str]) -> str | None:
    for criterion in success_criteria:
        normalized = criterion.lower()
        if any(
            skipped in normalized
            for skipped in (
                "page title",
                "browser title",
                "title shows",
                "title is",
                "url contains",
                "url updates",
                "url ending",
                "url ends",
                "browser loads",
                "browser navigates",
            )
        ):
            continue
        if not any(
            visible_hint in normalized
            for visible_hint in (
                "heading",
                "text",
                "visible",
                "content",
                "label",
                "button",
                "link",
                "field",
                "filters",
                "results",
            )
        ):
            continue
        example_match = re.search(r"e\.g\.,?\s*([^)\n]+)", criterion, flags=re.IGNORECASE)
        if example_match:
            return example_match.group(1).strip(" .'\"")
        quoted = re.findall(r"'([^']{4,})'", criterion)
        if quoted:
            return max((item.strip() for item in quoted), key=len)
    return None


def _normalize_click_target(target: str) -> str:
    parenthesized = re.search(r"\(([^()]+)\)\s*$", target)
    if not parenthesized:
        return target

    hint = parenthesized.group(1).strip().strip("`'\"")
    if not hint:
        return target
    if hint.startswith("/"):
        return f'a[href="{hint}"]'
    if hint.startswith(("#", ".", "[", "a[")) or "=" in hint:
        return hint
    return target
