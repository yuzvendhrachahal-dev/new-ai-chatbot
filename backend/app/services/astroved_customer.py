"""
AstroVed Customer Details Integration Service.
Prepares and submits customer details to the external AstroVed UserAccount API:
POST https://qawebservice.astroved.com/api/UserAccount/AddChatBotDetails

Security Constraints:
- Uses ASTROVED_JWT_TOKEN from the environment.
- Never prints, logs, exposes, returns, or hardcodes the JWT token.
- Validates required fields before dispatch.
- Handles network errors and non-200 responses safely without crashing.
- Never invoked automatically on product queries.
"""

import os
import re
import logging
import httpx
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_QA_ENDPOINT = "https://qawebservice.astroved.com/api/UserAccount/AddChatBotDetails"


class CustomerDetailsRequest(BaseModel):
    """
    Validation schema for AstroVed AddChatBotDetails API payload.
    """
    CustomerName: str = Field(..., min_length=2, max_length=150)
    CurrencyCode: str = Field(default="INR", min_length=3, max_length=5)
    CountryCode: str = Field(default="+91", min_length=1, max_length=10)
    MobileNo: str = Field(..., min_length=5, max_length=25)
    EmailAddress: EmailStr

    @field_validator("CustomerName")
    @classmethod
    def clean_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("CustomerName must not be empty.")
        return cleaned

    @field_validator("CurrencyCode")
    @classmethod
    def clean_currency(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not re.match(r"^[A-Z]{3,5}$", cleaned):
            raise ValueError("CurrencyCode must be 3-5 uppercase letters (e.g. INR, USD).")
        return cleaned

    @field_validator("CountryCode")
    @classmethod
    def clean_country_code(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned.startswith("+"):
            cleaned = f"+{cleaned}"
        return cleaned

    @field_validator("MobileNo")
    @classmethod
    def clean_mobile(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v.strip())
        if not cleaned.isdigit() or len(cleaned) < 5:
            raise ValueError("MobileNo must contain at least 5 digits.")
        return cleaned


def split_phone_number(phone_raw: str, default_country: str = "+91") -> Tuple[str, str]:
    """
    Splits a composite phone string (e.g. '+91 9876543210' or '+15551234567')
    into (country_code, mobile_no).
    """
    if not phone_raw:
        return default_country, ""

    cleaned = phone_raw.strip()
    if cleaned.startswith("+"):
        # Has explicit country prefix
        parts = cleaned.split(" ", 1)
        if len(parts) == 2:
            return parts[0].strip(), re.sub(r"[^\d]", "", parts[1])
        # Contiguous: +919876543210
        if cleaned.startswith("+91") and len(cleaned) > 5:
            return "+91", cleaned[3:]
        elif cleaned.startswith("+1") and len(cleaned) > 4:
            return "+1", cleaned[2:]
        elif cleaned.startswith("+44") and len(cleaned) > 5:
            return "+44", cleaned[3:]
        elif cleaned.startswith("+60") and len(cleaned) > 5:
            return "+60", cleaned[3:]
        elif cleaned.startswith("+65") and len(cleaned) > 5:
            return "+65", cleaned[3:]
        elif len(cleaned) >= 12:
            return cleaned[:3], cleaned[3:]

    # No country prefix
    digits_only = re.sub(r"[^\d]", "", cleaned)
    return default_country, digits_only


class AstroVedCustomerService:
    """
    Client for AstroVed AddChatBotDetails endpoint.
    Safely encapsulates JWT authorization and network communication.
    """
    def __init__(self, endpoint_url: Optional[str] = None):
        self._endpoint_url = endpoint_url or getattr(settings, "ASTROVED_QA_ENDPOINT", DEFAULT_QA_ENDPOINT)

    @property
    def token(self) -> str:
        return (getattr(settings, "ASTROVED_JWT_TOKEN", "") or os.getenv("ASTROVED_JWT_TOKEN", "")).strip()

    async def submit_customer_details(
        self,
        customer_name: str,
        currency_code: str = "INR",
        country_code: str = "+91",
        mobile_no: str = "",
        email_address: str = "",
        timeout: float = 8.0
    ) -> Dict[str, Any]:
        """
        Validates customer fields and submits to the QA webservice endpoint.
        Returns:
            dict with success (bool), status_code (int or None), and message (str).
            Guarantees no secrets or tokens are ever returned or logged.
        """
        # 1. Validate payload using Pydantic schema
        try:
            validated = CustomerDetailsRequest(
                CustomerName=customer_name,
                CurrencyCode=currency_code,
                CountryCode=country_code,
                MobileNo=mobile_no,
                EmailAddress=email_address
            )
        except Exception:
            fail_log = "[AstroVed Lead] Submission failed (Status: ValidationError)"
            print(fail_log, flush=True)
            logger.warning(fail_log)
            return {
                "success": False,
                "status_code": 422,
                "message": "Validation error: invalid customer details."
            }

        jwt_token = self.token
        if not jwt_token:
            skip_log = "[AstroVed Lead] Submission skipped (Status: MissingToken)"
            print(skip_log, flush=True)
            logger.warning(skip_log)
            return {
                "success": False,
                "status_code": None,
                "message": "ASTROVED_JWT_TOKEN is not configured in environment."
            }

        payload = validated.model_dump()

        # 2. Dispatch HTTP POST request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {jwt_token}"
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(
                    self._endpoint_url,
                    headers=headers,
                    json=payload
                )

                if res.status_code == 200:
                    try:
                        res_data = res.json()
                    except Exception:
                        res_data = {}

                    api_status_code = res_data.get("StatusCode") if isinstance(res_data, dict) else None
                    status_str = str(res_data.get("Status", "")).strip().lower() if isinstance(res_data, dict) else ""
                    msg_str = str(res_data.get("Message", "")).strip().lower() if isinstance(res_data, dict) else ""

                    # Confirm API response indicates success (StatusCode == 200 and successful status/message)
                    is_api_success = (
                        api_status_code == 200
                        and (
                            status_str in ("ok", "success")
                            or "success" in msg_str
                            or "inserted" in msg_str
                        )
                    )

                    if is_api_success:
                        success_log = "[AstroVed Lead] Customer details inserted successfully (StatusCode: 200)"
                        print(success_log, flush=True)
                        logger.info(success_log)
                        return {
                            "success": True,
                            "status_code": 200,
                            "message": res_data.get("Message") or "Customer details inserted successfully."
                        }
                    else:
                        status_cat = api_status_code if api_status_code is not None else "Rejected"
                        fail_log = f"[AstroVed Lead] Submission failed (Status: {status_cat})"
                        print(fail_log, flush=True)
                        logger.warning(fail_log)
                        return {
                            "success": False,
                            "status_code": api_status_code if isinstance(api_status_code, int) else 400,
                            "message": (res_data.get("Message") if isinstance(res_data, dict) else None) or "Customer details insertion rejected."
                        }
                else:
                    fail_log = f"[AstroVed Lead] Submission failed (Status: {res.status_code})"
                    print(fail_log, flush=True)
                    logger.warning(fail_log)
                    return {
                        "success": False,
                        "status_code": res.status_code,
                        "message": f"External API returned status {res.status_code}"
                    }

        except httpx.TimeoutException:
            fail_log = "[AstroVed Lead] Submission failed (Status: Timeout)"
            print(fail_log, flush=True)
            logger.warning(fail_log)
            return {
                "success": False,
                "status_code": 504,
                "message": "Connection to customer details service timed out."
            }
        except httpx.RequestError:
            fail_log = "[AstroVed Lead] Submission failed (Status: NetworkError)"
            print(fail_log, flush=True)
            logger.warning(fail_log)
            return {
                "success": False,
                "status_code": 502,
                "message": "Network error connecting to customer details service."
            }
        except Exception:
            fail_log = "[AstroVed Lead] Submission failed (Status: Error)"
            print(fail_log, flush=True)
            logger.warning(fail_log)
            return {
                "success": False,
                "status_code": 500,
                "message": "Unexpected error submitting customer details."
            }


astroved_customer_service = AstroVedCustomerService()
