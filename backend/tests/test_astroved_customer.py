"""
Tests for AstroVed Customer Details QA API preparation:
POST https://qawebservice.astroved.com/api/UserAccount/AddChatBotDetails

Security & Functional Verification:
- Validates required customer fields (CustomerName, CurrencyCode, CountryCode, MobileNo, EmailAddress).
- Uses ASTROVED_JWT_TOKEN from root .env without logging, returning, or leaking it.
- Handles non-200 responses, timeouts, and network errors safely.
- Never called automatically when someone asks about a product.
- Dedicated endpoint POST /api/customer/chatbot-details.
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport, Response

from app.main import app
from app.core.config import settings
from app.services.astroved_customer import (
    astroved_customer_service,
    CustomerDetailsRequest,
    split_phone_number
)


def test_split_phone_number_helper():
    """
    Verifies phone splitting into (country_code, mobile_no).
    """
    assert split_phone_number("+91 9876543210") == ("+91", "9876543210")
    assert split_phone_number("+1 5551234567") == ("+1", "5551234567")
    assert split_phone_number("+919876543210") == ("+91", "9876543210")
    assert split_phone_number("9876543210") == ("+91", "9876543210")


def test_customer_details_validation():
    """
    Verifies validation rules for customer details fields:
    - CustomerName required
    - CurrencyCode (3-5 uppercase letters)
    - CountryCode (starts with +)
    - MobileNo (at least 5 digits)
    - EmailAddress (valid email)
    """
    # Valid payload
    valid = CustomerDetailsRequest(
        CustomerName="Lakshmi Priya",
        CurrencyCode="inr",
        CountryCode="91",
        MobileNo="98765 43210",
        EmailAddress="lakshmi.priya@example.com"
    )
    assert valid.CustomerName == "Lakshmi Priya"
    assert valid.CurrencyCode == "INR"
    assert valid.CountryCode == "+91"
    assert valid.MobileNo == "9876543210"

    # Invalid email
    with pytest.raises(Exception):
        CustomerDetailsRequest(
            CustomerName="Test",
            CurrencyCode="INR",
            CountryCode="+91",
            MobileNo="9876543210",
            EmailAddress="not-an-email"
        )

    # Empty name
    with pytest.raises(Exception):
        CustomerDetailsRequest(
            CustomerName="",
            CurrencyCode="INR",
            CountryCode="+91",
            MobileNo="9876543210",
            EmailAddress="test@example.com"
        )

    # Invalid mobile (letters)
    with pytest.raises(Exception):
        CustomerDetailsRequest(
            CustomerName="Test",
            CurrencyCode="INR",
            CountryCode="+91",
            MobileNo="abcde",
            EmailAddress="test@example.com"
        )


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_submit_customer_details_success_mock(capsys):
    """
    Verifies successful submission handling with mock 200 response:
    - Confirms '[AstroVed Lead] Customer details inserted successfully (StatusCode: 200)' is printed/logged.
    - Ensures no customer PII (name, email, phone) or JWT is logged.
    """
    mock_response = Response(
        status_code=200,
        json={"StatusCode": 200, "Status": "OK", "Message": "Customer details inserted successfully."}
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = await astroved_customer_service.submit_customer_details(
            customer_name="Suresh Kumar",
            currency_code="INR",
            country_code="+91",
            mobile_no="9876543210",
            email_address="suresh@example.com"
        )

        assert res["success"] is True
        assert res["status_code"] == 200
        assert "Customer details inserted successfully." in res["message"]

        # Verify exact required log output
        captured = capsys.readouterr()
        assert "[AstroVed Lead] Customer details inserted successfully (StatusCode: 200)" in captured.out

        # Verify no customer PII or JWT is present in printed output
        assert "Suresh Kumar" not in captured.out
        assert "suresh@example.com" not in captured.out
        assert "9876543210" not in captured.out
        jwt_token = astroved_customer_service.token
        if jwt_token:
            assert jwt_token not in captured.out

        # Verify Authorization header had Bearer token
        called_headers = mock_post.call_args.kwargs["headers"]
        assert "Authorization" in called_headers
        assert called_headers["Authorization"].startswith("Bearer ")
        assert called_headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_transport_200_with_api_rejection_does_not_log_success(capsys):
    """
    Requirement:
    'Log only after confirming the API response indicates success; do not log success merely because HTTP transport returned 200.'
    """
    mock_response = Response(
        status_code=200,
        json={"StatusCode": 400, "Status": "Error", "Message": "Duplicate customer record."}
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = await astroved_customer_service.submit_customer_details(
            customer_name="Suresh Kumar",
            currency_code="INR",
            country_code="+91",
            mobile_no="9876543210",
            email_address="suresh@example.com"
        )

        assert res["success"] is False
        assert res["status_code"] == 400

        # MUST NOT log success
        captured = capsys.readouterr()
        assert "Customer details inserted successfully" not in captured.out
        # Logs concise failure category
        assert "[AstroVed Lead] Submission failed (Status: 400)" in captured.out

        # No customer PII or JWT in logs
        assert "Suresh Kumar" not in captured.out
        assert "suresh@example.com" not in captured.out
        assert "9876543210" not in captured.out
        jwt_token = astroved_customer_service.token
        if jwt_token:
            assert jwt_token not in captured.out


@pytest.mark.asyncio
async def test_submit_customer_details_non_200_safe_handling(capsys):
    """
    Verifies that external non-200 responses log concise failure category without PII or JWT.
    """
    mock_response = Response(status_code=401, json={"Message": "Unauthorized"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        res = await astroved_customer_service.submit_customer_details(
            customer_name="Suresh Kumar",
            currency_code="INR",
            country_code="+91",
            mobile_no="9876543210",
            email_address="suresh@example.com"
        )

        assert res["success"] is False
        assert res["status_code"] == 401

        captured = capsys.readouterr()
        assert "[AstroVed Lead] Submission failed (Status: 401)" in captured.out
        assert "Suresh Kumar" not in captured.out
        assert "suresh@example.com" not in captured.out


@pytest.mark.asyncio
async def test_submit_customer_details_network_timeout(capsys):
    """
    Verifies safe handling of network timeout without crashing, logging concise category.
    """
    import httpx
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timed out")):
        res = await astroved_customer_service.submit_customer_details(
            customer_name="Suresh Kumar",
            currency_code="INR",
            country_code="+91",
            mobile_no="9876543210",
            email_address="suresh@example.com"
        )

        assert res["success"] is False
        assert res["status_code"] == 504
        assert "timed out" in res["message"].lower()

        captured = capsys.readouterr()
        assert "[AstroVed Lead] Submission failed (Status: Timeout)" in captured.out
        assert "Suresh Kumar" not in captured.out
        assert "suresh@example.com" not in captured.out


@pytest.mark.asyncio
async def test_dedicated_customer_details_api_endpoint():
    """
    Verifies the dedicated FastAPI endpoint POST /api/customer/chatbot-details.
    """
    transport = ASGITransport(app=app)
    mock_result = {
        "success": True,
        "status_code": 200,
        "message": "Customer details inserted successfully."
    }

    with patch.object(astroved_customer_service, "submit_customer_details", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = mock_result

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(f"{settings.API_V1_STR}/customer/chatbot-details", json={
                "CustomerName": "Ananya Sharma",
                "CurrencyCode": "INR",
                "CountryCode": "+91",
                "MobileNo": "9876543210",
                "EmailAddress": "ananya@example.com"
            })

            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert "inserted successfully" in data["message"].lower()

            # Verify submit_customer_details was called with validated arguments
            mock_submit.assert_awaited_once_with(
                customer_name="Ananya Sharma",
                currency_code="INR",
                country_code="+91",
                mobile_no="9876543210",
                email_address="ananya@example.com"
            )

            # Verify token is not in response
            jwt_token = astroved_customer_service.token
            if jwt_token:
                assert jwt_token not in str(data)


@pytest.mark.asyncio
async def test_asking_about_product_never_calls_customer_details_api():
    """
    CRITICAL REQUIREMENT:
    'Never call this endpoint automatically just because someone asks about a product.'
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        start_res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
            "name": "Dev",
            "email": "dev@example.com",
            "mobile": "+91 9876543210"
        })
        conv_id = start_res.json()["conversation_id"]

        # Spy on submit_customer_details during chat/send
        with patch.object(astroved_customer_service, "submit_customer_details", new_callable=AsyncMock) as spy_submit:
            send_res = await ac.post(f"{settings.API_V1_STR}/chat/send", json={
                "conversation_id": conv_id,
                "message": "What is the price of Ganesha homam and can you give me a product link?"
            })
            assert send_res.status_code == 200

            # MUST NOT HAVE BEEN CALLED
            spy_submit.assert_not_called()


@pytest.mark.asyncio
async def test_lead_api_failure_does_not_prevent_chat_from_opening():
    """
    CRITICAL REQUIREMENT:
    'Confirm lead API failure does not prevent the chatbot from opening, and the JWT is never logged or exposed.'
    """
    transport = ASGITransport(app=app)
    # Simulate QA lead API network failure / timeout
    with patch.object(astroved_customer_service, "submit_customer_details", side_effect=RuntimeError("QA endpoint timeout")):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(f"{settings.API_V1_STR}/chat/start", json={
                "name": "Pooja Sharma",
                "email": "pooja.sharma@example.com",
                "mobile": "+91 9123456789"
            })

            # Chatbot consultation must still start successfully with 200 OK
            assert res.status_code == 200
            data = res.json()
            assert "conversation_id" in data
            assert "welcome_message" in data
            assert data["customer"]["name"] == "Pooja Sharma"

            # Assert JWT token is never present in response
            jwt_token = astroved_customer_service.token
            if jwt_token:
                assert jwt_token not in str(data)
