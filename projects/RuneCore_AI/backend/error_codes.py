#!/usr/bin/env python3
"""
Error Code Definitions for RuneCore AI Service

Convention: [Type][Origin][Component][Subcomponent][Number]

Type (1 char):
    E = Error
    W = Warning
    I = Info

Origin (1 char):
    A = AI Service

Component (1 char):
    B = Backend
    F = Frontend
    S = Setup
    N = Network

Subcomponent (1 char):
    A = Async/Agent Manager
    B = Backend general (inference)
    C = Cache
    M = Model
    S = Security
    # = General

Number (2 digits): 01-99

Examples:
    EABA01 = Error + AI Service + Backend + Async + 01
    WABM01 = Warning + AI Service + Backend + Model + 01
    IABS01 = Info + AI Service + Backend + Setup + 01
"""

# === BACKEND - INFERENCE (ABB) ===
ERROR_CODES = {
    # Info codes
    "IABB01": "Inference request received",
    "IABB02": "Inference response sent successfully",
    "IABB03": "Chat request processed",
    "IABB04": "Agent loaded for inference",
    "IABB05": "Conversation context built",

    # Warning codes
    "WABB01": "Slow inference response",
    "WABB02": "Retrying inference request",
    "WABB03": "Using fallback model",

    # Error codes
    "EABB01": "Inference failed - model loading issue",
    "EABB02": "No available model for inference",
    "EABB03": "Model loading failed - unsupported format",
    "EABB04": "Inference timeout",
    "EABB05": "Upstream AI service unavailable or unresponsive",
    "EABB06": "Invalid inference request payload",
    "EABB07": "Agent not found for inference",
    "EABB08": "Empty response from model",

    # === BACKEND - ASYNC/AGENT MANAGER (ABA) ===
    # Info codes
    "IABA01": "Async request cancelled by user",
    "IABA02": "Async worker started",
    "IABA03": "Async request queued",

    # Warning codes
    "WABA01": "Async queue growing large",
    "WABA02": "Worker processing slowly",

    # Error codes
    "EABA01": "Agent worker request processing error",
    "EABA02": "Agent worker loop error",
    "EABA03": "Ollama returned non-200 status",
    "EABA04": "Async request timeout",
    "EABA05": "Async request processing exception",
    "EABA06": "Failed to start async workers",
    "EABA07": "Failed to submit async request",

    # === BACKEND - CACHE (ABC) ===
    # Info codes
    "IABC01": "Cache initialized",
    "IABC02": "Conversation cached",
    "IABC03": "Cache cleared for agent",

    # Warning codes
    "WABC01": "Cache miss - no conversation history",
    "WABC02": "Redis unavailable, using fallback",

    # Error codes
    "EABC01": "Cache read error",
    "EABC02": "Cache write error",
    "EABC03": "Cache connection failed",
    "EABC04": "Cache serialization error",

    # === BACKEND - MODEL (ABM) ===
    # Info codes
    "IABM01": "Model list retrieved",
    "IABM02": "Model pull initiated",
    "IABM03": "Model pull completed",
    "IABM04": "Model deleted",

    # Warning codes
    "WABM01": "Failed to fetch models",
    "WABM02": "Model pull taking longer than expected",
    "WABM03": "Model not found in cache",

    # Error codes
    "EABM01": "Model list fetch failed",
    "EABM02": "Model deletion failed",
    "EABM03": "Model pull failed",
    "EABM04": "Model not found",
    "EABM05": "Invalid model name",
    "EABM06": "Model pull timeout",

    # === BACKEND - SECURITY (ABS) ===
    # Info codes
    "IABS01": "Rate limit check passed",
    "IABS02": "Input sanitization applied",

    # Warning codes
    "WABS01": "Potentially suspicious input pattern detected",
    "WABS02": "Rate limit warning - approaching limit",

    # Error codes
    "EABS01": "Rate limit exceeded",
    "EABS02": "Input validation failed",
    "EABS03": "Invalid request format",
    "EABS04": "Request too large",

    # === BACKEND - GENERAL (AB#) ===
    # Info codes
    "IAB#01": "Backend service started",
    "IAB#02": "Health check successful",
    "IAB#03": "Agent created",
    "IAB#04": "Agent updated",
    "IAB#05": "Agent deleted",

    # Warning codes
    "WAB#01": "Backend operation slow",
    "WAB#02": "Non-critical error occurred",

    # Error codes
    "EAB#01": "Backend initialization error",
    "EAB#02": "Database connection error",
    "EAB#03": "Agent creation failed",
    "EAB#04": "Agent update failed",
    "EAB#05": "Agent deletion failed",
    "EAB#06": "Internal server error",

    # === FRONTEND ERRORS (AFX) ===
    # Info codes
    "IAFX01": "Frontend loaded",
    "IAFX02": "User message sent",

    # Warning codes
    "WAFX01": "Frontend connection unstable",

    # Error codes
    "EAFX01": "Frontend rendering error",
    "EAFX02": "Frontend API call failed",
    "EAFX03": "Frontend state error",

    # === NETWORK ERRORS (ANX) ===
    # Info codes
    "IANX01": "Network request completed",

    # Warning codes
    "WANX01": "Network latency high",
    "WANX02": "Retrying network request",

    # Error codes
    "EANX01": "Network connection failed",
    "EANX02": "Network timeout",
    "EANX03": "DNS resolution failed",
}


def get_error_explanation(code: str) -> str:
    """Get the explanation for an error code"""
    return ERROR_CODES.get(code, f"Unknown error code: {code}")


def get_error_type(code: str) -> str:
    """Get the type (Error/Warning/Info) from a code"""
    if not code:
        return "unknown"
    type_char = code[0].upper()
    return {
        "E": "error",
        "W": "warning",
        "I": "info",
    }.get(type_char, "unknown")


def get_error_origin(code: str) -> str:
    """Get the origin service from a code"""
    if not code or len(code) < 2:
        return "unknown"
    origin_char = code[1].upper()
    return {
        "A": "ai_service",
        "R": "runecore",
        "G": "runeguard",
        "M": "runemind",
        "P": "runepulse",
    }.get(origin_char, "unknown")


def get_error_component(code: str) -> str:
    """Get the component from a code"""
    if not code or len(code) < 3:
        return "unknown"
    comp_char = code[2].upper()
    return {
        "B": "backend",
        "F": "frontend",
        "S": "setup",
        "N": "network",
    }.get(comp_char, "unknown")


def format_error(code: str, message: str = None, extra: dict = None) -> dict:
    """Format an error for API response"""
    return {
        "error_code": code,
        "error_type": get_error_type(code),
        "error_origin": get_error_origin(code),
        "error_component": get_error_component(code),
        "message": message or get_error_explanation(code),
        "extra": extra or {},
    }
