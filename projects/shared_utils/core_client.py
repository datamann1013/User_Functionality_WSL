"""Helper client for interacting with RuneCore Core (registration, PKI)"""
from typing import Optional, Dict, Any
import os
import requests


class CoreClientError(Exception):
    pass


class CoreClient:
    def __init__(self, core_url: Optional[str] = None, cert: Optional[str] = None, key: Optional[str] = None, ca_path: Optional[str] = None, disable_mtls: bool = False):
        self.core_url = core_url or os.environ.get("RUNECORE_CORE_URL", "https://127.0.0.1:11440")
        self.cert = (cert, key) if cert and key and not disable_mtls else None
        self.verify = ca_path if ca_path and not disable_mtls else (False if disable_mtls else True)
        # allow env var override for testing convenience
        if os.environ.get("RUNECORE_DISABLE_MTLS") in ("1", "true", "True"):
            self.cert = None
            self.verify = False

    def register_service(self, info: Dict[str, Any], timeout: int = 5) -> Dict[str, Any]:
        url = f"{self.core_url}/api/v1/services/register"
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(url, json=info, headers=headers, timeout=timeout, cert=self.cert, verify=self.verify)
        except requests.RequestException as e:
            raise CoreClientError(f"network error during register: {e}")
        except Exception as e:
            # wrap any unexpected exception from requests or monkeypatched functions
            raise CoreClientError(f"network error during register: {e}")

        try:
            body = resp.json()
        except ValueError:
            raise CoreClientError(f"invalid json response: {resp.text}")

        if resp.status_code >= 400:
            raise CoreClientError(f"error from core: {resp.status_code} {body}")

        return body

    def sign_csr(self, csr_pem: str, days_valid: int = 7, timeout: int = 5) -> str:
        url = f"{self.core_url}/api/v1/pki/sign"
        payload = {"csr_pem": csr_pem, "days_valid": days_valid}
        try:
            resp = requests.post(url, json=payload, timeout=timeout, cert=self.cert, verify=self.verify)
        except requests.RequestException as e:
            raise CoreClientError(f"network error during sign_csr: {e}")
        except Exception as e:
            # wrap any unexpected exception from requests or monkeypatched functions
            raise CoreClientError(f"network error during sign_csr: {e}")

        try:
            body = resp.json()
        except ValueError:
            raise CoreClientError(f"invalid json response: {resp.text}")

        if resp.status_code >= 400 or not body.get("ok"):
            raise CoreClientError(f"error from core signing: {resp.status_code} {body}")

        return body.get("cert_pem")
