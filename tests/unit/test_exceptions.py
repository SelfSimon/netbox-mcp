from client.exceptions import (
    NetBoxClientError,
    NetBoxConfigurationError,
    NetBoxConnectionError,
    NetBoxNoBranchError,
    NetBoxNotFoundError,
    NetBoxPermissionError,
    NetBoxValidationError,
)


def test_all_client_exceptions_derive_from_base():
    for exc_class in (
        NetBoxConfigurationError,
        NetBoxNotFoundError,
        NetBoxValidationError,
        NetBoxPermissionError,
        NetBoxConnectionError,
        NetBoxNoBranchError,
    ):
        assert issubclass(exc_class, NetBoxClientError)


def test_validation_error_carries_errors_payload():
    exc = NetBoxValidationError("bad data", errors={"name": ["required"]})

    assert exc.errors == {"name": ["required"]}
    assert str(exc) == "bad data"


def test_validation_error_defaults_errors_to_empty_dict():
    exc = NetBoxValidationError("bad data")

    assert exc.errors == {}
