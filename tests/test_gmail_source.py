import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weekly_clean_fuels_digest import gmail_source


def test_expired_gmail_token_refresh_uses_supported_request_timeout(
    monkeypatch, tmp_path
):
    token_path = tmp_path / "runtime" / "token.json"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gmail_source, "PROJECT_ROOT", tmp_path)

    observed_timeouts = []

    class FakeRequest:
        def __init__(self):
            pass

        def __call__(self, url, method="GET", body=None, headers=None, timeout=120):
            observed_timeouts.append(timeout)

    class FakeCredentials:
        expired = True
        refresh_token = "refresh-token"
        valid = True

        @classmethod
        def from_authorized_user_file(cls, path, scopes):
            return cls()

        def refresh(self, request):
            request("https://oauth.example/token", method="POST")

        def to_json(self):
            return "{}"

    monkeypatch.setattr(gmail_source, "Request", FakeRequest)
    monkeypatch.setattr(gmail_source, "Credentials", FakeCredentials)
    monkeypatch.setattr(
        gmail_source, "AuthorizedHttp", lambda *args, **kwargs: object()
    )
    monkeypatch.setattr(gmail_source.httplib2, "Http", lambda **kwargs: object())
    monkeypatch.setattr(gmail_source, "build", lambda *args, **kwargs: "service")

    service = gmail_source.gmail_service(
        {
            "ai": {"request_timeout_seconds": 37},
            "paths": {"gmail_token": "runtime/token.json"},
        }
    )

    assert service == "service"
    assert observed_timeouts == [37]


def test_invalid_refresh_token_falls_back_to_oauth_login(monkeypatch, tmp_path):
    token_path = tmp_path / "runtime" / "token.json"
    credentials_path = tmp_path / "runtime" / "credentials.json"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("{}", encoding="utf-8")
    credentials_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gmail_source, "PROJECT_ROOT", tmp_path)

    class ExpiredCredentials:
        expired = True
        refresh_token = "revoked-token"
        valid = False

        def refresh(self, request):
            raise gmail_source.RefreshError(
                "invalid_grant: Token has been expired or revoked."
            )

    class FreshCredentials:
        expired = False
        refresh_token = None
        valid = True

        def to_json(self):
            return "fresh-token"

    class CredentialsFactory:
        @staticmethod
        def from_authorized_user_file(path, scopes):
            return ExpiredCredentials()

    class OAuthFlow:
        def run_local_server(self, port):
            assert port == 0
            return FreshCredentials()

    monkeypatch.setattr(gmail_source, "Credentials", CredentialsFactory)
    monkeypatch.setattr(gmail_source, "Request", lambda: lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gmail_source.InstalledAppFlow,
        "from_client_secrets_file",
        lambda path, scopes: OAuthFlow(),
    )
    monkeypatch.setattr(
        gmail_source, "AuthorizedHttp", lambda *args, **kwargs: object()
    )
    monkeypatch.setattr(gmail_source.httplib2, "Http", lambda **kwargs: object())
    monkeypatch.setattr(gmail_source, "build", lambda *args, **kwargs: "service")

    service = gmail_source.gmail_service(
        {
            "ai": {"request_timeout_seconds": 37},
            "paths": {
                "gmail_token": "runtime/token.json",
                "gmail_credentials": "runtime/credentials.json",
            },
        }
    )

    assert service == "service"
    assert token_path.read_text(encoding="utf-8") == "fresh-token"
