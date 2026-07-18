from schemas.choices import DeviceStatus, IPAddressStatus, SiteStatus, VLANStatus


def test_choices_are_plain_strings():
    assert DeviceStatus.ACTIVE == "active"
    assert SiteStatus.RETIRED == "retired"
    assert IPAddressStatus.DHCP == "dhcp"
    assert VLANStatus.DEPRECATED == "deprecated"
