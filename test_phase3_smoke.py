"""
Phase 3 smoke test — verifies the refactored external-integration code
paths work end-to-end through the API.

Tests:
  1. Registration still works (+ welcome email fires without error)
  2. Login and token generation
  3. Profile image upload — validation (missing file, bad type, size)
  4. Password reset request — returns 200 (anti-enumeration)
  5. Password reset confirm — token validation flow
  6. All existing auth endpoints still function correctly
"""

import io
import requests
import sys
import time

BASE = "http://localhost:8000/api/v1"
AUTH = f"{BASE}/auth"
TS = str(int(time.time()))
passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label} — {detail}")


def main():
    global passed, failed

    # ---------------------------------------------------------------
    print("\n=== REGISTRATION (triggers welcome email) ===")
    # ---------------------------------------------------------------
    r = requests.post(f"{AUTH}/register/", json={
        "username": f"phase3_{TS}",
        "email": f"phase3_{TS}@example.com",
        "password": "Phase3Pass!99",
        "password_confirm": "Phase3Pass!99",
    })
    check("Register returns 201", r.status_code == 201, f"{r.status_code} {r.text[:200]}")
    data = r.json()
    check("Has tokens", "tokens" in data and "access" in data["tokens"])
    token = data["tokens"]["access"]
    headers = {"Authorization": f"Bearer {token}"}

    # ---------------------------------------------------------------
    print("\n=== LOGIN ===")
    # ---------------------------------------------------------------
    r = requests.post(f"{AUTH}/login/", json={
        "username": f"phase3_{TS}",
        "password": "Phase3Pass!99",
    })
    check("Login returns 200", r.status_code == 200, f"{r.status_code}")

    # ---------------------------------------------------------------
    print("\n=== PROFILE IMAGE UPLOAD — VALIDATION ===")
    # ---------------------------------------------------------------

    # No file
    r = requests.post(f"{AUTH}/profile/upload-image/", headers=headers)
    check("No image → 400", r.status_code == 400, f"{r.status_code}")
    check("Error message", "No image" in r.json().get("detail", ""), r.json())

    # Wrong content type
    fake_txt = io.BytesIO(b"not an image")
    r = requests.post(
        f"{AUTH}/profile/upload-image/",
        headers=headers,
        files={"image": ("test.txt", fake_txt, "text/plain")},
    )
    check("Bad type → 400", r.status_code == 400, f"{r.status_code}")
    check("Type error message", "Unsupported" in r.json().get("detail", ""), r.json())

    # File too large (create a >5 MB payload)
    big = io.BytesIO(b"\x00" * (5 * 1024 * 1024 + 1))
    r = requests.post(
        f"{AUTH}/profile/upload-image/",
        headers=headers,
        files={"image": ("big.png", big, "image/png")},
    )
    check("Oversize → 400", r.status_code == 400, f"{r.status_code} {r.text[:200]}")
    check("Size error message", "exceeds" in r.json().get("detail", "").lower() or "limit" in r.json().get("detail", "").lower(), r.json())

    # ---------------------------------------------------------------
    print("\n=== PASSWORD RESET REQUEST (anti-enumeration) ===")
    # ---------------------------------------------------------------

    # Existing email
    r = requests.post(f"{AUTH}/password-reset/", json={
        "email": f"phase3_{TS}@example.com",
    })
    check("Reset existing email → 200", r.status_code == 200, f"{r.status_code}")
    check("Generic message", "If an account" in r.json().get("detail", ""))

    # Non-existing email (must ALSO return 200 — anti-enumeration)
    r = requests.post(f"{AUTH}/password-reset/", json={
        "email": "doesnotexist@example.com",
    })
    check("Reset unknown email → 200", r.status_code == 200, f"{r.status_code}")
    check("Same generic message", "If an account" in r.json().get("detail", ""))

    # ---------------------------------------------------------------
    print("\n=== PASSWORD RESET CONFIRM — TOKEN VALIDATION ===")
    # ---------------------------------------------------------------

    # Invalid uid/token
    r = requests.post(f"{AUTH}/password-reset/confirm/", json={
        "uid": "invaliduid",
        "token": "invalidtoken",
        "new_password": "NewPass123!",
        "new_password_confirm": "NewPass123!",
    })
    check("Invalid reset link → 400", r.status_code == 400, f"{r.status_code}")

    # ---------------------------------------------------------------
    print("\n=== PROFILE GET/PATCH still works ===")
    # ---------------------------------------------------------------
    r = requests.get(f"{AUTH}/profile/", headers=headers)
    check("Profile GET → 200", r.status_code == 200 and r.json()["username"] == f"phase3_{TS}")

    r = requests.patch(f"{AUTH}/profile/", json={"bio": "Phase 3 test bio"}, headers=headers)
    check("Profile PATCH → 200", r.status_code == 200 and r.json()["bio"] == "Phase 3 test bio")

    # ---------------------------------------------------------------
    print("\n=== CHANGE PASSWORD still works ===")
    # ---------------------------------------------------------------
    r = requests.post(f"{AUTH}/change-password/", json={
        "old_password": "Phase3Pass!99",
        "new_password": "ChangedPass!99",
        "new_password_confirm": "ChangedPass!99",
    }, headers=headers)
    check("Change password → 200", r.status_code == 200, f"{r.status_code}")

    # Re-login with new password
    r = requests.post(f"{AUTH}/login/", json={
        "username": f"phase3_{TS}",
        "password": "ChangedPass!99",
    })
    check("Login with new password → 200", r.status_code == 200, f"{r.status_code}")

    # ---------------------------------------------------------------
    print("\n=== LOGOUT still works ===")
    # ---------------------------------------------------------------
    new_token = r.json()["tokens"]
    r = requests.post(f"{AUTH}/logout/", json={
        "refresh": new_token["refresh"],
    }, headers={"Authorization": f"Bearer {new_token['access']}"})
    check("Logout → 200", r.status_code == 200, f"{r.status_code}")

    # ---------------------------------------------------------------
    print("\n=== UNAUTHENTICATED ACCESS ===")
    # ---------------------------------------------------------------
    r = requests.get(f"{AUTH}/profile/")
    check("Profile without token → 401", r.status_code == 401)

    # ==================================================================
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failed:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
