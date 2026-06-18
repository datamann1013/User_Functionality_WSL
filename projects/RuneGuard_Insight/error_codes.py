#!/usr/bin/env python3
"""
Error Code Definitions for RuneGuard_Insight

Convention: [Type][Origin][Component][Subcomponent][Number]

Type (1 char):
    E = Error
    W = Warning
    I = Info

Origin (1 char):
    G = RuneGuard

Component (1 char):
    I = Insight

Subcomponent (1 char):
    D = Docker socket / stats collection
    T = Telemetry shipping
    R = Core registration / heartbeat
    H = Health endpoint
    # = General

Number (2 digits): 01-99

Examples:
    EGID01 = Error   + RuneGuard + Insight + Docker  + 01
    IGIR01 = Info    + RuneGuard + Insight + Register + 01
    WGIT01 = Warning + RuneGuard + Insight + Telemetry + 01
"""

ERROR_CODES = {
    # === General (#) ===
    "IGI#01": "RuneGuard_Insight started",
    "IGI#02": "RuneGuard_Insight stopping",

    # === Docker socket / stats (D) ===
    "IGID01": "Docker client connected",
    "WGID01": "Docker client unavailable, retrying with backoff",
    "WGID02": "Failed to read stats for a container (skipped)",
    "EGID01": "Docker socket unreachable after all retries",

    # === Telemetry shipping (T) ===
    "IGIT01": "Container metrics shipped to CoreMemory",
    "WGIT01": "Telemetry POST failed (non-fatal)",

    # === Core registration / heartbeat (R) ===
    "IGIR01": "Registered with RuneCore_Core",
    "WGIR01": "Core registration failed (limb mode)",
    "WGIR02": "Core heartbeat failed",

    # === Health endpoint (H) ===
    "IGIH01": "Health server started",
    "EGIH01": "Health server failed to start",
}
