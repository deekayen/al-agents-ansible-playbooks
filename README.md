# deekayen.alagent

[![CI](https://github.com/deekayen/al-agents-ansible-playbooks/actions/workflows/ci.yml/badge.svg)](https://github.com/deekayen/al-agents-ansible-playbooks/actions/workflows/ci.yml) [![Ansible Galaxy](https://img.shields.io/badge/galaxy-deekayen.alagent-blue.svg)](https://galaxy.ansible.com/ui/standalone/roles/deekayen/alagent/) [![Project Status: Inactive – The project has reached a stable, usable state but is no longer being actively developed; support/maintenance will be provided as time allows.](https://www.repostatus.org/badges/latest/inactive.svg)](https://www.repostatus.org/#inactive) ![Apache 2.0 license](https://img.shields.io/badge/license-Apache--2.0-blue)

An Ansible role that installs the Alert Logic agent on Linux and Windows hosts, provisions it with a registration key, and forwards the local syslog stream to it.

On Linux, the role installs the vendor's `LATEST` package from `scc.alertlogic.net/software/` (a `.deb` on Debian and Ubuntu, an `.rpm` on the RedHat family and SUSE) after trusting the Alert Logic signing key. It then runs `/etc/init.d/al-agent configure` and `/etc/init.d/al-agent provision`, writes an rsyslog or syslog-ng drop-in that sends all messages to `127.0.0.1:1514`, labels TCP 1514 as `syslogd_port_t` when SELinux is enabled, and starts the `al-agent` service. On Windows, it downloads `al_agent-LATEST.msi` to `C:\TEMP` and installs it with `win_package`, which passes the provisioning options as MSI properties.

The repository is named `al-agents-ansible-playbooks`, but it is a single role, and its Galaxy name is `deekayen.alagent`.

## Requirements

- ansible-core 2.15 or newer on the controller.
- The `community.general` collection for the SELinux and SUSE tasks. Windows targets also need `ansible.windows`.
- Outbound HTTPS from the target to `scc.alertlogic.net`.
- Privilege escalation on Linux targets. Run the play with `become: true`; the role installs packages and writes under `/etc`.
- Fact gathering left on. The role branches on `ansible_facts.os_family`, `ansible_facts.architecture`, and `ansible_facts.selinux`.

## Supported platforms

| Platform | Versions |
| --- | --- |
| EL (Rocky Linux in CI) | 9, 10 |
| Amazon Linux | 2023 |
| Debian | 12 (bookworm), 13 (trixie) |
| Ubuntu | 22.04 (jammy), 24.04 (noble), 26.04 (resolute) |
| Windows | 2016, 2019, 2022 |

Molecule installs the agent on `rockylinux9`, `rockylinux10`, `amazonlinux2023`, `ubuntu2204`, `ubuntu2404`, `ubuntu2604`, `debian12`, and `debian13` containers. CI does not apply the role to Windows. The role also has a SUSE install path and `vars/Suse.yml`, but `meta/main.yml` does not list SUSE and CI does not run it.

## Installation

From Ansible Galaxy:

```bash
ansible-galaxy role install deekayen.alagent
ansible-galaxy collection install community.general
```

Or pin it in `requirements.yml`:

```yaml
---
roles:
  - name: deekayen.alagent
    src: https://github.com/deekayen/al-agents-ansible-playbooks.git
    scm: git
    version: main

collections:
  - name: community.general
  - name: ansible.windows
```

```bash
ansible-galaxy install -r requirements.yml
```

## Role variables

| Variable | Default | Description |
| --- | --- | --- |
| `disable_gpg_check` | `false` | Passed to `dnf` as `disable_gpg_check` when installing the RPM on RedHat-family hosts. Workaround for [alertlogic/al-agents-ansible-playbooks#32](https://github.com/alertlogic/al-agents-ansible-playbooks/issues/32), where RPM signature checks broke installs. It has no effect on Debian, Ubuntu, SUSE, or Windows. |
| `al_agent_for_imaging` | `false` | Install the agent without starting the service, so an instance snapshot can become a machine image. On Windows, it passes `INSTALL_ONLY=1 PROV_NOW=0` to the MSI. See [Known issues](#known-issues) for Linux. |

### Optional variables

These have no default. The role checks each with `is defined`, and `tasks/assert.yml` fails the play if one is set to an empty string.

| Variable | Description |
| --- | --- |
| `al_agent_registration_key` | Alert Logic registration key. Passed as `--key` to `al-agent provision` on Linux and as `PROV_KEY` on Windows. `meta/argument_specs.yml` describes it as optional in AWS and Azure deployments. Keep it in Ansible Vault or a secrets lookup; no task sets `no_log`, so it appears in verbose output. |
| `al_agent_egress_host` | Single point of egress, such as a NAT instance. Passed as `--host` on Linux and `SENSOR_HOST` on Windows. |
| `al_agent_egress_port` | Integer from 1 to 65535, enforced by `tasks/assert.yml`. Passed as `--port` on Linux only when `al_agent_egress_host` is also set, and as `SENSOR_PORT` on Windows. |
| `al_agent_proxy_url` | Proxy for agent traffic. Passed as `--proxy` on Linux and `USE_PROXY` on Windows. |

`vars/Debian.yml`, `vars/RedHat.yml`, and `vars/Suse.yml` hold the package URLs, architecture mapping, and signing key fingerprint for each OS family; they are internal values.

## Behavior

- The Linux configure and provision commands run only when `/var/alertlogic/etc/host_key.pem` is absent, and they report `changed` every time they run. On Windows, an existing `C:\Program Files (x86)\Common Files\AlertLogic\host_key.pem` switches the MSI to `INSTALL_ONLY=1 PROV_NOW=0`.
- The packages are the vendor's `LATEST` builds. `apt`, `dnf`, and `zypper` install them when the package is absent and do not pin a version.
- On Debian and Ubuntu, the signing key goes to `/etc/apt/trusted.gpg.d/alertlogic.asc` instead of `apt-key`. On the RedHat family, `rpm_key` imports it and checks fingerprint `9a2a3e9a817127b121b2b2fb00802f0e0186cc36`.
- The rsyslog drop-in is `/etc/rsyslog.d/alertlogic.conf`. For syslog-ng, the role writes `/etc/syslog-ng/conf.d/alertlogic.conf` and adds an `include` line to `/etc/syslog-ng/syslog-ng.conf`. The role detects syslog-ng by the presence of `/etc/init.d/syslog-ng`.
- Provisioning notifies a restart of `al-agent`; logger changes restart rsyslog or reload syslog-ng.
- The Windows installer stays in `C:\TEMP\al_agent-LATEST.msi`, and the role creates `C:\TEMP` if it is missing.

## Dependencies

None.

## Example playbook

```yaml
---
- name: Install the Alert Logic agent.
  hosts: alertlogic_monitored
  become: true

  vars:
    al_agent_registration_key: "{{ vault_al_agent_registration_key }}"
    al_agent_egress_host: egress.example.internal
    al_agent_egress_port: 443

  roles:
    - deekayen.alagent
```

`egress.example.internal` is a placeholder for an egress host, and `vault_al_agent_registration_key` is a placeholder for a vaulted variable.

## Tags

| Tag | Tasks |
| --- | --- |
| `always` | Input validation and the OS family `include_vars`. |
| `al_agent` | The include of all Linux tasks. |
| `windows` | The include of all Windows tasks. |
| `install_agent` | The include of the Linux package install tasks. |
| `install_al_agent` | Linux package installs and the service start. |
| `configure_al_agent` | Host key check and `al-agent configure`. |
| `provision_al_agent` | Host key check, `al-agent provision`, and the logger configuration include. |
| `rsyslog`, `syslog_ng`, `configure_al_agent_syslog` | Logger detection and drop-in files. |
| `selinux` | The SELinux port rule. |

`--skip-tags` works on any of these, and Molecule uses `--skip-tags provision_al_agent,configure_al_agent`. `--tags` does not select inner tags alone, because each task file is pulled in by an `include_tasks` that carries different tags. `--tags install_al_agent` runs only the validation tasks; `--tags al_agent,install_agent,install_al_agent` reaches the package installs but skips the untagged signing key import.

## Known issues

- `defaults/main.yml` describes `al_agent_for_imaging` as leaving the agent unprovisioned, but `tasks/provision_agent.yml` runs the same `/etc/init.d/al-agent provision` command when it is `true`. Only the restart handler and the service start are skipped. `tasks/configure_agent.yml` also runs in imaging mode.
- `al_agent_initscript` and `al_agent_syslog_ng_source` are set in each `vars/*.yml` file, but no task or template reads them. `templates/etc/syslog-ng/alertlogic.conf` hardcodes `source(s_sys)`.
- `meta/main.yml` lists Windows platforms, but neither `meta/main.yml` nor `molecule/default/requirements.yml` declares the `ansible.windows` collection that `tasks/_windows.yml` uses.

## Development

CI runs on every push to `main` and every pull request (see `.github/workflows/ci.yml`):

1. Lint: installs `community.general` from `molecule/default/requirements.yml`, then runs `ansible-lint --profile production` and `flake8 molecule/`.
2. Molecule: converge, idempotence, and testinfra verification in Docker against each Linux distribution listed above. `molecule.yml` sets `ANSIBLE_SKIP_TAGS=provision_al_agent,configure_al_agent`, since those steps need a real registration key, so CI does not exercise provisioning or the syslog drop-ins.

To run the same checks locally with Docker available:

```bash
pip3 install ansible-core ansible-lint flake8 molecule "molecule-plugins[docker]" docker pytest-testinfra
ansible-galaxy install -r molecule/default/requirements.yml
ansible-lint --profile production
flake8 molecule/
MOLECULE_DISTRO=rockylinux9 molecule test
```

`MOLECULE_DISTRO` selects a `geerlingguy/docker-<distro>-ansible` image. The testinfra checks in `molecule/default/tests/test_default.py` confirm that the `al-agent` package is installed, `/var/alertlogic/lib/agent/bin/al-agent` exists with mode `0755`, the signing key is trusted (the apt keyring file, or key ID `0186cc36` in the RPM database), and the `al-agent` service is enabled.

### Repository layout

| Path | Purpose |
| --- | --- |
| `tasks/main.yml` | Runs validation, then the Windows or Linux task file. |
| `tasks/assert.yml` | Input validation, tagged `always`. |
| `tasks/_linux.yml` | Orders the Linux install, configure, provision, logger, SELinux, and service steps. |
| `tasks/_windows.yml` | Builds MSI properties, downloads, and installs the Windows agent. |
| `tasks/install_agent.yml` | Signing key import and package install per OS family. |
| `tasks/configure_agent.yml`, `tasks/provision_agent.yml` | `al-agent configure` and `al-agent provision`. |
| `tasks/configure_loggers.yml`, `tasks/_rsyslog.yml`, `tasks/_syslog_ng.yml` | Syslog forwarding to port 1514. |
| `tasks/selinux.yml` | SELinux port rule for TCP 1514. |
| `templates/etc/` | rsyslog and syslog-ng drop-ins. |
| `vars/` | Per-OS-family package URLs and key fingerprint. |
| `defaults/main.yml` | The two user-facing variables with defaults. |
| `meta/argument_specs.yml` | Argument spec, including the optional variables. |
| `molecule/default/` | Molecule scenario: `prepare.yml`, `converge.yml`, requirements, and testinfra tests. |
| `.github/workflows/` | `ci.yml` for lint and Molecule, `release.yml` for Galaxy import. |

## Releases

Pushing a git tag runs `.github/workflows/release.yml`, which imports the tagged commit into Ansible Galaxy as `deekayen.alagent`. The import needs a `GALAXY_API_KEY` repository or organization secret.

## License

Apache 2.0. See [LICENSE](LICENSE).

## Authors

Muram Mohamed, Justin Early, and Craig Davis wrote the original role for Alert Logic at [alertlogic/al-agents-ansible-playbooks](https://github.com/alertlogic/al-agents-ansible-playbooks). This repository is forked from [cbdr/al-agents-ansible-playbooks](https://github.com/cbdr/al-agents-ansible-playbooks) and maintained by [David Norman](https://github.com/deekayen). Sponsorship links are in [.github/FUNDING.yml](.github/FUNDING.yml).
