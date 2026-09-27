"""Testinfra checks for the Alert Logic agent role."""

AGENT_BIN = "/var/alertlogic/lib/agent/bin/al-agent"
KEY_ID = "0186cc36"


def test_agent_package_installed(host):
    assert host.package("al-agent").is_installed


def test_agent_binary(host):
    assert host.file("/var/alertlogic").is_directory
    agent = host.file(AGENT_BIN)
    assert agent.is_file
    assert agent.mode == 0o755


def test_signing_key_trusted(host):
    if host.exists("apt-get"):
        key = host.file("/etc/apt/trusted.gpg.d/alertlogic.asc")
        assert key.is_file
        assert key.mode == 0o644
    else:
        keys = host.check_output("rpm -q gpg-pubkey --qf '%{VERSION}\\n'")
        assert KEY_ID in keys.lower().split()


def test_agent_service_enabled(host):
    assert host.service("al-agent").is_enabled
